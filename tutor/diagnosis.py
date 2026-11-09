"""Photo diagnosis workflow: validate -> rate limit -> Claude vision -> Diagnosis -> optional Problem (FR-33)."""
import time

from django.conf import settings
from django.core.exceptions import ValidationError

from analytics.services import track
from garden.images import clean_photo
from garden.services import log_problem

from . import guardrails, vision
from .context import GardenContext
from .models import Diagnosis

DAILY_LIMIT = 10           # PRD 6.6: 10 photo diagnoses per user per day


class DiagnosisError(Exception):
    def __init__(self, message, status):
        super().__init__(message)
        self.message, self.status = message, status


def run_diagnosis(user, upload, user_plant=None, note=""):
    """Return a saved Diagnosis, or raise DiagnosisError with a user-facing message."""
    try:
        photo = clean_photo(upload)
    except ValidationError as exc:
        raise DiagnosisError(exc.message, 400) from exc
    if guardrails.rate_limited(f"diagnosis:{user.pk}", limit=DAILY_LIMIT):
        raise DiagnosisError("You have used today's photo diagnoses. Please come back tomorrow.", 429)

    note = guardrails.clean_text(note, 300)
    start = time.perf_counter()
    try:
        result, prompt_tokens, completion_tokens = vision.diagnose(photo.read(), GardenContext(user).build(user_plant), note)
    except vision.VisionUnavailable as exc:
        raise DiagnosisError("Photo diagnosis is unavailable right now. Please try again in a moment.", 503) from exc
    photo.seek(0)
    diagnosis = Diagnosis(user=user, user_plant=user_plant, note=note, result=result, model_name=settings.DIAGNOSIS_MODEL,
                          prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                          latency_ms=round((time.perf_counter() - start) * 1000))
    diagnosis.image.save("photo.jpg", photo, save=True)
    track("diagnosis_created", user, plant_scoped=bool(user_plant))
    return diagnosis


def _description(result):
    lines = [f"{i['name']} ({i['confidence']} confidence): {i['reasoning']}" for i in result["issues"]]
    if result["immediate_actions"]:
        lines.append("What to do now: " + "; ".join(result["immediate_actions"]))
    if result["watch_for"]:
        lines.append("Watch for: " + "; ".join(result["watch_for"]))
    return "\n".join(lines)


def save_to_problem(diagnosis, user_plant):
    """Save a diagnosis to the plant's Problem log. Saving twice returns the same Problem."""
    if diagnosis.problem_id:
        return diagnosis.problem
    result = diagnosis.result
    title = result["issues"][0]["name"][:120] if result["issues"] else "Photo check"
    problem = log_problem(user_plant, title=title, description=_description(result), photo=diagnosis.image.name,
                          category=result["category"], severity=result["severity"])
    diagnosis.problem, diagnosis.user_plant = problem, user_plant
    diagnosis.save(update_fields=["problem", "user_plant"])
    return problem
