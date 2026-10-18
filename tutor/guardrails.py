"""Shared safety checks for every AI feature (local model and external API).

Cleaning and JSON validation mirror llm-test/ai_prototype.ipynb on purpose: the benchmark
numbers only hold if the app prepares input and checks output the same way.

Typical use in a view:

    ok, reason = check_input(text)
    if not ok or rate_limited(request.user.id):
        ...show an error...
    cleaned = clean_text(text)
    raw = <call the model>
    result = parse_and_validate(raw, "care")       # always a dict
    if result.get("error"):    ...show FALLBACK_MESSAGE...
    elif result.get("refused"): ...show result["reason"]...
"""
import json
import re

from django.core.cache import cache

MAX_INPUT_CHARS = 600      # text sent to the model is cut to this (same cap as the notebook)
MAX_RAW_CHARS = 2000       # anything longer is rejected outright instead of truncated
MIN_INPUT_CHARS = 2
RATE_LIMIT_PER_HOUR = 30   # AI requests allowed per user per hour

FALLBACK_MESSAGE = "Sorry, I couldn't produce a reliable answer. Please try rephrasing your question."

TOPICS = {"watering", "pests", "soil", "harvest", "seeds", "other"}
DIFFICULTY = {"easy", "medium", "hard"}

# Cheap first line of defence against prompt injection. The model is told to refuse these too,
# so this is a pre-filter, not the only protection.
INJECTION_PATTERNS = [re.compile(p, re.IGNORECASE) for p in (
    r"ignore (all |any )?(the )?(previous|prior|above) (instructions|text|prompt|rules)",
    r"ignore (all |any )?(the )?(text|content|messages?) above",
    r"disregard (all |any |your |the )?(previous |prior )?(instructions|rules)",
    r"system prompt",
    r"you are now",
    r"developer mode",
    r"jailbreak",
)]


def clean_text(text, max_chars=MAX_INPUT_CHARS):
    """Strip control characters and HTML, collapse whitespace and '!!!!', and cap the length."""
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"([!?.])\1{2,}", r"\1", text)
    return text[:max_chars]


def check_input(text):
    """Return (ok, reason). Run this before calling any model or API."""
    if not isinstance(text, str):
        return False, "Please enter some text."
    if len(text) > MAX_RAW_CHARS:
        return False, f"That is too long. Please keep it under {MAX_RAW_CHARS} characters."
    cleaned = clean_text(text)
    if len(cleaned) < MIN_INPUT_CHARS:
        return False, "Please enter a question or some text."
    if any(p.search(cleaned) for p in INJECTION_PATTERNS):
        return False, "That request can't be processed. Please ask a gardening question."
    return True, ""


def rate_limited(user_id, limit=RATE_LIMIT_PER_HOUR, window=3600):
    """True when this user already used up their AI requests for the current window."""
    key = f"ai_rate:{user_id}"
    if cache.add(key, 1, window):
        return False
    try:
        count = cache.incr(key)
    except ValueError:              # key expired between add() and incr()
        cache.set(key, 1, window)
        count = 1
    return count > limit


def extract_json(text):
    """First JSON object in the text (models sometimes add chatter or ```json fences around it)."""
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            obj, _ = decoder.raw_decode(text[match.start():])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return None


def schema_ok(obj, task):
    """task is 'care' (tutor answer) or 'summary' (post summary). A refusal is always valid."""
    if obj is None:
        return False
    if obj.get("refused") is True:
        return isinstance(obj.get("reason"), str)
    if task == "care":
        steps = obj.get("steps")
        return (isinstance(obj.get("answer"), str) and isinstance(steps, list) and len(steps) >= 1
                and all(isinstance(s, str) for s in steps) and obj.get("difficulty") in DIFFICULTY)
    if task == "summary":
        return isinstance(obj.get("summary"), str) and obj.get("topic") in TOPICS
    return False


def parse_and_validate(raw, task):
    """Turn raw model output into a safe dict. Never raises.

    Returns the model's JSON when it is valid (including {"refused": true, "reason": ...}),
    otherwise {"error": True, "message": FALLBACK_MESSAGE}.
    """
    obj = extract_json(raw) if isinstance(raw, str) else None
    if schema_ok(obj, task):
        return obj
    return {"error": True, "message": FALLBACK_MESSAGE}
