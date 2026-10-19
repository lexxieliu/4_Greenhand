"""Google Gemini client (external API) used to write post summaries.

Talks to the public REST endpoint with `requests`, so no extra package is needed. The API key is read
from settings.GEMINI_API_KEY (.env -> API_KEY) and sent in a header, never in the URL, so it cannot
end up in server logs. Every failure becomes a GeminiError the caller can handle; nothing here
ever crashes a page.
"""
import logging

import requests
from django.conf import settings

from tutor import prompts
from tutor.guardrails import clean_text, parse_and_validate

logger = logging.getLogger(__name__)

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class GeminiError(Exception):
    """The Gemini API is not configured, unreachable, or returned something unusable."""


def is_configured():
    return bool(settings.GEMINI_API_KEY)


def _headers():
    return {"x-goog-api-key": settings.GEMINI_API_KEY, "Content-Type": "application/json"}


def _error_text(response):
    try:
        message = response.json().get("error", {}).get("message", "")
    except ValueError:
        message = response.text
    return str(message)[:200]


def generate_text(system_prompt, user_text, max_output_tokens=1024):
    """One Gemini call. Returns the model's text. Raises GeminiError on any problem."""
    if not is_configured():
        raise GeminiError("Gemini API key is not configured (set API_KEY in .env).")
    url = f"{BASE_URL}/models/{settings.GEMINI_MODEL}:generateContent"
    body = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_text}]}],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": max_output_tokens,     # generous: some models spend tokens "thinking"
            "responseMimeType": "application/json",
        },
    }
    try:
        response = requests.post(url, json=body, headers=_headers(), timeout=settings.GEMINI_TIMEOUT)
    except requests.exceptions.RequestException as exc:
        logger.warning("Gemini request failed: %s", type(exc).__name__)
        raise GeminiError(f"Could not reach Gemini ({type(exc).__name__}).") from exc
    if response.status_code != 200:
        detail = _error_text(response)
        logger.warning("Gemini returned HTTP %s: %s", response.status_code, detail)
        raise GeminiError(f"Gemini returned HTTP {response.status_code}: {detail}")
    try:
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        logger.warning("Gemini response had an unexpected shape")
        raise GeminiError("Gemini returned an unexpected response.") from exc


def summarize(post_text):
    """Summarize a community post. Returns a validated dict:
    {"summary", "topic"}, {"refused": True, "reason"}, or {"error": True, "message"}.
    Reuses the exact system prompt and JSON format the local model was benchmarked with."""
    user_text = prompts.USER_PREFIX["summary"] + clean_text(post_text)
    raw = generate_text(prompts.SYSTEM["summary"], user_text)
    return parse_and_validate(raw, "summary")


def list_models():
    """Names of models this key can use for generateContent (for the check_gemini command)."""
    if not is_configured():
        raise GeminiError("Gemini API key is not configured (set API_KEY in .env).")
    try:
        response = requests.get(f"{BASE_URL}/models", headers=_headers(), params={"pageSize": 100},
                                timeout=settings.GEMINI_TIMEOUT)
    except requests.exceptions.RequestException as exc:
        raise GeminiError(f"Could not reach Gemini ({type(exc).__name__}).") from exc
    if response.status_code != 200:
        raise GeminiError(f"Gemini returned HTTP {response.status_code}: {_error_text(response)}")
    models = response.json().get("models", [])
    return sorted(m["name"].removeprefix("models/") for m in models
                  if "generateContent" in m.get("supportedGenerationMethods", []))
