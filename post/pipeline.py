"""Hybrid pipeline for new community posts: local model filters, Gemini writes the summary.

    1. LOCAL model (Qwen2.5-3B, free, runs on our server) checks the post is on-topic and safe.
       Spam / off-topic / injection posts are rejected here, so they never cost an API call.
    2. GEMINI (external API) writes the final one-sentence summary for posts that pass.
    3. If Gemini is not configured or fails, the local model's own summary is used instead.
       If both fail the post is still published, just without a summary.

Nothing in here raises for model/API problems; the caller only looks at PipelineResult.status.
"""
import logging
from dataclasses import dataclass

from tutor import llm

from . import gemini

logger = logging.getLogger(__name__)

OK = "ok"
REJECTED = "rejected"


@dataclass
class PipelineResult:
    status: str                 # OK or REJECTED
    summary: str = ""
    topic: str = ""
    source: str = "none"        # "gemini", "local" or "none"
    message: str = ""           # why it was rejected, or a note for the user


def _rejected(data):
    reason = data.get("reason") or "It does not look like a gardening post."
    return PipelineResult(status=REJECTED, message=reason)


def process_post(text):
    # Step 1: local filter (best effort: if the local model is down we still try Gemini).
    local = None
    try:
        local = llm.generate_json("summary", text)
    except llm.LLMUnavailable:
        logger.warning("Local model unavailable; skipping the local filter")
    if local and local.get("refused"):
        return _rejected(local)
    local_summary = local if local and not local.get("error") else None

    # Step 2: external API writes the summary.
    if gemini.is_configured():
        try:
            data = gemini.summarize(text)
        except gemini.GeminiError:
            data = None
        if data and data.get("refused"):
            return _rejected(data)
        if data and not data.get("error"):
            return PipelineResult(OK, data["summary"], data["topic"], source="gemini")

    # Step 3: fall back to the local model's summary, or publish without one.
    if local_summary:
        return PipelineResult(OK, local_summary["summary"], local_summary["topic"], source="local",
                              message="The online summarizer was unavailable, so our local AI wrote this summary.")
    return PipelineResult(OK, source="none", message="Your post was published, but no AI summary could be created.")
