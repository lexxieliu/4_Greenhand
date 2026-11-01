"""The tutor pipeline (PRD 6.4 A): guardrails -> context -> retrieval -> local LLM -> validation -> log.

ask_tutor() is the only entry point. Views, the JSON API and the evaluation command all call it and
always get a plain dict back (never an exception), with "status" one of:
    "answer"   - answer, steps, difficulty, sources, safety_warning ...
    "refused"  - reason (off-topic or injection, decided by the model)
    "error"    - message for the user, error_kind for the code
"""
import json
import logging
import time

from django.conf import settings

from greenhand import mock_data as data

from . import guardrails, knowledge, llm, prompts
from .context import build_context, detect_plant, find_plant
from .models import AITutorLog

logger = logging.getLogger(__name__)

RATE_LIMIT_MESSAGE = "You have used today's tutor questions. Please come back tomorrow."
UNAVAILABLE_MESSAGE = "The AI tutor is unavailable right now. Please try again in a moment."
TIMEOUT_MESSAGE = "The tutor took too long to answer. Please try a shorter or simpler question."


def _error(question, message, kind, **extra):
    return {"status": "error", "question": question, "message": message, "error_kind": kind, **extra}


def _retrieve(question, plant):
    """Top notes for the question. The plant's species is added to vague scoped questions
    ("Should I water today?") so its own guide can be found. Retrieval failing is not fatal:
    the tutor then answers without notes and says it is not certain."""
    species = data.CATALOG_BY_SLUG[plant["plant_slug"]]["common_name"] if plant else ""
    query = question if species.lower() in question.lower() else f"{question} {species}".strip()
    try:
        return knowledge.search(query)
    except Exception:
        logger.exception("Retrieval failed; answering without notes")
        return []


def _sources(hits, cited):
    return [{"id": h.chunk.id, "title": h.chunk.title, "score": h.score, "cited": h.chunk.id in cited} for h in hits]


def ask_tutor(question, plant_id="", user=None, rate_key=None):
    """Answer one tutor question. plant_id scopes it to a garden plant (FR-32); without it the plant
    is detected from the question. Answers and refusals are logged to AITutorLog when a user is given."""
    ok, reason = guardrails.check_input(question)
    if not ok:
        return _error(question, reason, "invalid_input")
    if rate_key and guardrails.rate_limited(rate_key):
        return _error(question, RATE_LIMIT_MESSAGE, "rate_limited")

    cleaned = guardrails.clean_text(question)
    plant = find_plant(plant_id) if plant_id else detect_plant(cleaned)
    hits = _retrieve(cleaned, plant)
    messages = prompts.build_messages(cleaned, build_context(plant), hits)

    start = time.perf_counter()
    try:
        raw = llm.generate(messages)
    except llm.LLMUnavailable:
        return _error(question, UNAVAILABLE_MESSAGE, "unavailable")
    latency_ms = round((time.perf_counter() - start) * 1000)

    parsed = guardrails.parse_and_validate(raw, {h.chunk.id for h in hits})
    meta = {"plant": {"id": plant["id"], "nickname": plant["nickname"]} if plant else None,
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
        }
    if user is not None:
        AITutorLog.objects.create(user=user, question=question, answer=json.dumps(result), thinking_process=raw)
    return result
