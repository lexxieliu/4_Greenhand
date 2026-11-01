"""Safety checks around the tutor's model call (ported from the A6 tutor, commit ab9d2b5).

Input side:   check_input() and rate_limited() run before any model work; clean_text() is what
              the model actually sees.
Output side:  parse_and_validate() turns raw model text into a safe dict and never raises;
              safety_warning() adds the PRD 8.3 warning on edible / toxic / chemical topics.

Typical use (see services.ask_tutor):

    ok, reason = check_input(text)
    if not ok or rate_limited(key): ...show an error, no model call...
    result = parse_and_validate(raw, allowed_sources)   # always a dict
    if result.get("error"):    ...show FALLBACK_MESSAGE...
    elif result.get("refused"): ...show result["reason"]...
"""
import json
import re

from django.core.cache import cache

MAX_INPUT_CHARS = 600      # text sent to the model is cut to this (same cap as the A6 notebook)
MAX_RAW_CHARS = 2000       # anything longer is rejected outright instead of truncated (PRD 2.2 chat cap)
MIN_INPUT_CHARS = 2
DAILY_LIMIT = 50           # PRD 6.6: 50 tutor messages per user per day
MAX_STEPS = 4

FALLBACK_MESSAGE = "Sorry, I couldn't produce a reliable answer. Please try rephrasing your question."

DIFFICULTY = {"easy", "medium", "hard"}

# Cheap first line of defence against prompt injection. The model is told to refuse these too,
# so this is a pre-filter, not the only protection.
INJECTION_PATTERNS = [re.compile(p, re.IGNORECASE) for p in (
    r"ignore (all |any )?(the |your )?(previous|prior|above) (instructions|text|prompt|rules)",
    r"ignore (all |any )?(the )?(text|content|messages?) above",
    r"disregard (all |any |your |the )?(previous |prior )?(instructions|rules)",
    r"system prompt",
    r"you are now",
    r"developer mode",
    r"jailbreak",
)]

# PRD 8.3: extra warning when an answer involves eating plants, toxicity, pesticides or chemicals.
SAFETY_PATTERN = re.compile(
    r"\b(eat|eating|edible|safe to eat|toxic|toxicity|poison\w*|pesticide\w*|insecticide\w*|fungicide\w*|"
    r"herbicide\w*|chemical\w*|bleach|neem|weed ?killer|my (dog|cat|kids?|child|children)|pets?)\b",
    re.IGNORECASE,
)
SAFETY_WARNING = (
    "Do not eat any plant or plant part unless you have positively identified it using a reliable source. "
    "Always follow the product label when using fertilizers or pesticides, and keep them away from children "
    "and pets. For poisoning or health emergencies, contact a medical professional or poison control right away."
)
DISCLAIMER = "AI-generated advice may be inaccurate. Verify before acting, especially for safety-related questions."


def clean_text(text, max_chars=MAX_INPUT_CHARS):
    """Strip control characters and HTML, collapse whitespace and '!!!!', and cap the length."""
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f​-‏⁠﻿]", "", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"([!?.])\1{2,}", r"\1", text)
    return text[:max_chars]


def check_input(text):
    """Return (ok, reason). Run this before calling any model."""
    if not isinstance(text, str):
        return False, "Please enter a question."
    if len(text) > MAX_RAW_CHARS:
        return False, f"That is too long. Please keep it under {MAX_RAW_CHARS} characters."
    cleaned = clean_text(text)
    if len(cleaned) < MIN_INPUT_CHARS:
        return False, "Please enter a question."
    if any(p.search(cleaned) for p in INJECTION_PATTERNS):
        return False, "That request can't be processed. Please ask a gardening question."
    return True, ""


def rate_limited(key, limit=None, window=24 * 3600):
    """True when this user (or session) already used up today's tutor questions."""
    limit = limit or DAILY_LIMIT
    cache_key = f"tutor_rate:{key}"
    if cache.add(cache_key, 1, window):
        return False
    try:
        count = cache.incr(cache_key)
    except ValueError:              # key expired between add() and incr()
        cache.set(cache_key, 1, window)
        count = 1
    return count > limit


def extract_json(text):
    """First JSON object in the text (models sometimes add chatter or ```json fences around it)."""
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            obj, _ = decoder.raw_decode(text[match.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def schema_ok(obj):
    """A tutor answer {"answer", "steps", "difficulty", "sources"?} or a refusal {"refused", "reason"}.
    "steps" may be empty: yes/no and timing questions often have nothing to do (A9 eval cases T4, T6)."""
    if obj is None:
        return False
    if obj.get("refused") is True:
        return isinstance(obj.get("reason"), str)
    steps = obj.get("steps")
    return (isinstance(obj.get("answer"), str) and obj["answer"].strip() != ""
            and isinstance(steps, list) and all(isinstance(s, str) for s in steps)
            and obj.get("difficulty") in DIFFICULTY)


def parse_and_validate(raw, allowed_sources=()):
    """Turn raw model output into a safe dict. Never raises.

    Returns the model's JSON when it is valid (including {"refused": true, "reason": ...}),
    otherwise {"error": True, "message": FALLBACK_MESSAGE}. Cited sources that were not in the
    retrieved notes (hallucinated ids) are dropped, and steps are capped at MAX_STEPS.
    """
    obj = extract_json(raw) if isinstance(raw, str) else None
    if not schema_ok(obj):
        return {"error": True, "message": FALLBACK_MESSAGE}
    if obj.get("refused") is True:
        return {"refused": True, "reason": obj["reason"]}
    cited = obj.get("sources") if isinstance(obj.get("sources"), list) else []
    return {
        "answer": obj["answer"].strip(),
        "steps": [s.strip() for s in obj["steps"] if s.strip()][:MAX_STEPS],
        "difficulty": obj["difficulty"],
        "sources": [s for s in cited if s in allowed_sources],
    }


def safety_warning(*texts):
    """The PRD 8.3 safety warning if the question or answer touches a high-risk topic, else ''."""
    return SAFETY_WARNING if any(SAFETY_PATTERN.search(t or "") for t in texts) else ""
