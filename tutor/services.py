"""The tutor pipeline (PRD 6.4 A): guardrails -> context -> retrieval -> local LLM -> validation -> log.

ask_tutor() is the only entry point. Views, the JSON API and the evaluation command all call it and
always get a plain dict back (never an exception), with "status" one of:
    "answer"   - answer, steps, difficulty, sources, safety_warning ...
    "refused"  - reason (off-topic or injection, decided by the model)
    "error"    - message for the user, error_kind for the code
"""
import logging
import re
import time

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from analytics.services import track
from garden.models import Garden, Problem

from . import guardrails, knowledge, llm, prompts
from .context import GardenContext
from .models import ChatMessage, ChatSession

logger = logging.getLogger(__name__)

RATE_LIMIT_MESSAGE = "You have used today's tutor questions. Please come back tomorrow."
UNAVAILABLE_MESSAGE = "The AI tutor is unavailable right now. Please try again in a moment."
TIMEOUT_MESSAGE = "The tutor took too long to answer. Please try a shorter or simpler question."


def _error(question, message, kind, **extra):
    return {"status": "error", "question": question, "message": message, "error_kind": kind, **extra}


HISTORY_TURNS = 2        # earlier exchanges sent to the model; it is small, so context is kept short
# Questions that describe something wrong get a one-click "log this problem" action (FR-35).
PROBLEM_WORDS = re.compile(
    r"\b(yellow\w*|brown\w*|wilt\w*|spots?|spotted|holes?|droop\w*|dying|dead|mold\w*|mould\w*|aphids?|pests?|bugs?|"
    r"rot\w*|curl\w*|sick|disease\w*|fung\w*)\b", re.IGNORECASE)


def _retrieve(question, species):
    """Top notes for the question. The plant's species is added to vague scoped questions
    ("Should I water today?") so its own guide can be found. Retrieval failing is not fatal:
    the tutor then answers without notes and says it is not certain."""
    query = question if species.lower() in question.lower() else f"{question} {species}".strip()
    try:
        return knowledge.search(query)
    except Exception:
        logger.exception("Retrieval failed; answering without notes")
        return []


def _sources(hits, cited):
    return [{"id": h.chunk.id, "title": h.chunk.title, "score": h.score, "cited": h.chunk.id in cited} for h in hits]


def _history(session):
    """Last turns of the conversation as plain text. Stored text is cleaned again: it is data, not instructions."""
    if session is None:
        return ""
    recent = list(session.messages.order_by("-created_at", "-id")[:HISTORY_TURNS * 2])
    return "\n".join(f"{m.role}: {guardrails.clean_text(m.content, 200)}" for m in reversed(recent))


def _suggested_actions(question, described):
    if described and PROBLEM_WORDS.search(question):
        return [{"type": "log_problem", "label": f"Log this problem on {described['nickname']}", "done": False}]
    return []


def _save_turn(user, session, question, plant, result, raw, context_text, messages):
    """Store both sides of the exchange and fill in the ids the UI needs for rating."""
    prompt_tokens, completion_tokens = llm.usage(messages, raw)
    with transaction.atomic():
        if session is None:
            session = ChatSession.objects.create(user=user, title=question[:120],
                                                 scoped_plant=plant if isinstance(plant, Garden) else None)
        asked = ChatMessage.objects.create(session=session, role="user", content=question)
        answer = ChatMessage.objects.create(
            session=session, role="assistant", content=result.get("answer") or result.get("reason", ""), result=result,
            raw_output=raw, context_snapshot=context_text, retrieved_chunks=result.get("sources", []),
            suggested_actions=result.get("suggested_actions", []), model_name=result["model"],
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, latency_ms=result["latency_ms"],
        )
        session.last_message_at = timezone.now()
        session.save(update_fields=["last_message_at"])
    result.update(session_id=session.pk, question_id=asked.pk, message_id=answer.pk)
    track("tutor_message_sent", user, session_id=session.pk, plant_scoped=bool(plant))


def ask_tutor(question, plant_id="", user=None, rate_key=None, session=None, source=None):
    """Answer one tutor question. plant_id scopes it to a garden plant (FR-32); without it the session's plant
    is used, or the plant is detected from the question. Answers and refusals are stored as ChatMessages
    when a user is given. source replaces the user's garden with fixed data (used by evaluate_tutor)."""
    ok, reason = guardrails.check_input(question)
    if not ok:
        return _error(question, reason, "invalid_input")
    if rate_key and guardrails.rate_limited(rate_key):
        return _error(question, RATE_LIMIT_MESSAGE, "rate_limited")

    source = source or GardenContext(user)
    cleaned = guardrails.clean_text(question)
    plant_id = plant_id or (session.scoped_plant_id if session else "")
    plant = source.find(plant_id) if plant_id else source.detect(cleaned)
    described = source.describe(plant) if plant else None
    hits = _retrieve(cleaned, described["species"] if described else "")
    context_text = source.build(plant)
    messages = prompts.build_messages(cleaned, context_text, hits, _history(session))

    start = time.perf_counter()
    try:
        raw = llm.generate(messages)
    except llm.LLMUnavailable:
        return _error(question, UNAVAILABLE_MESSAGE, "unavailable")
    latency_ms = round((time.perf_counter() - start) * 1000)

    parsed = guardrails.parse_and_validate(raw, {h.chunk.id for h in hits})
    meta = {"plant": {"id": described["id"], "nickname": described["nickname"]} if described else None,
            "latency_ms": latency_ms, "model": settings.LOCAL_MODEL_ID}
    if parsed.get("error"):
        timed_out = latency_ms >= settings.TUTOR_TIMEOUT_SECONDS * 1000
        return _error(question, TIMEOUT_MESSAGE if timed_out else parsed["message"],
                      "timeout" if timed_out else "invalid_output", raw=raw, **meta)

    if parsed.get("refused"):
        result = {"status": "refused", "question": question, "reason": parsed["reason"], **meta}
    else:
        result = {
            "status": "answer", "question": question, **meta,
            "answer": parsed["answer"], "steps": parsed["steps"], "difficulty": parsed["difficulty"],
            "sources": _sources(hits, parsed["sources"]),
            "grounded": bool(hits),
            "safety_warning": guardrails.safety_warning(question, parsed["answer"], " ".join(parsed["steps"])),
            "disclaimer": guardrails.DISCLAIMER,
            "suggested_actions": _suggested_actions(cleaned, described),
        }
    if user is not None:
        _save_turn(user, session, question, plant, result, raw, context_text, messages)
    return result


def apply_log_problem(message):
    """Carry out a confirmed "log this problem" action (FR-35). Returns the Problem, or None if not applicable.
    The action is marked done, so a double click cannot log the problem twice."""
    action = next((a for a in message.suggested_actions if a["type"] == "log_problem" and not a["done"]), None)
    plant = message.result.get("plant")
    if action is None or plant is None:
        return None
    asked = message.session.messages.filter(role="user", pk__lt=message.pk).last()
    garden = message.session.user.my_garden_plants.filter(pk=plant["id"]).first()
    if asked is None or garden is None:
        return None
    with transaction.atomic():
        problem = Problem.objects.create(garden=garden, title=asked.content[:120], description=message.content)
        action["done"] = True
        message.save(update_fields=["suggested_actions"])
    return problem


def suggest_for_post(body, plant_name=""):
    """Short AI suggestion for a community question (FR-54), or "" when the model cannot give a reliable one.
    The post is untrusted text from another user: only its cleaned text reaches the prompt, as data."""
    if not guardrails.check_input(body)[0]:
        return ""
    cleaned = guardrails.clean_text(body)
    hits = _retrieve(cleaned, plant_name)
    garden = f"Community post about: {plant_name}" if plant_name else "Community post; no garden data."
    try:
        parsed = guardrails.parse_and_validate(llm.generate(prompts.build_messages(cleaned, garden, hits)),
                                               {h.chunk.id for h in hits})
    except llm.LLMUnavailable:
        return ""
    if parsed.get("error") or parsed.get("refused"):
        return ""
    return " ".join([parsed["answer"], *parsed["steps"]])
