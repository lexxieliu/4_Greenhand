import json
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from .context import GardenContext
from .diagnosis import DiagnosisError, run_diagnosis, save_to_problem
from .forms import DiagnosisForm, QuestionForm, SaveDiagnosisForm
from .models import ChatMessage, ChatSession, Diagnosis
from .services import apply_log_problem, ask_tutor

SESSION_LIST_SIZE = 6
ERROR_STATUS = {"invalid_input": 400, "rate_limited": 429, "invalid_output": 502, "unavailable": 503, "timeout": 504}


def _json_login_required(view):
    """Like login_required, but fetch() callers get JSON they can show instead of a login page redirect."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"status": "error", "error_kind": "login_required",
                                 "message": "Please log in to use the tutor."}, status=401)
        return view(request, *args, **kwargs)
    return wrapper


def _public(result):
    """Drop the raw model text before a result leaves the server."""
    public = {k: v for k, v in result.items() if k != "raw"}
    if "message_id" in public:
        public["feedback_url"] = reverse("tutor:feedback", args=[public["message_id"]])
    return public


def _owned_session(user, session_id):
    return ChatSession.objects.filter(user=user, pk=session_id).first() if str(session_id or "").isdigit() else None


@login_required
@require_http_methods(["GET", "POST"])
def ask(request):
    """AI Gardening Tutor page (FR-30/32): question + optional plant scope -> grounded answer, kept in a session."""
    user = request.user
    source = request.POST if request.method == "POST" else request.GET
    session = _owned_session(user, source.get("session"))
    result = None
    if request.method == "POST":
        form = QuestionForm(request.POST, user=user)
        if form.is_valid():
            result = _public(ask_tutor(form.cleaned_data["question"], form.cleaned_data["plant"], user=user,
                                       rate_key=user.pk, session=session))
            session = session or _owned_session(user, result.get("session_id"))
    else:
        form = QuestionForm(user=user, initial={"question": request.GET.get("q", ""), "plant": request.GET.get("plant", "")})
    thread = []
    if session:     # the answer just given is shown in full below the form, not repeated in the thread
        thread = session.messages.filter(role__in=("user", "assistant")).exclude(
            pk__in=[result.get("question_id"), result.get("message_id")] if result else [])
    return render(request, "tutor/ask.html", {
        "form": form, "result": result, "session": session, "thread": thread,
        "sessions": ChatSession.objects.filter(user=user)[:SESSION_LIST_SIZE],
    })


@_json_login_required
@require_POST
def api_ask(request):
    """JSON endpoint for the dashboard chat and the My Garden drawer: {"question", "plant", "session"} -> result."""
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "error_kind": "invalid_input", "message": "Invalid request."}, status=400)
    if not isinstance(body, dict):
        return JsonResponse({"status": "error", "error_kind": "invalid_input", "message": "Invalid request."}, status=400)
    user = request.user
    result = ask_tutor(body.get("question"), str(body.get("plant") or ""), user=user, rate_key=user.pk,
                       session=_owned_session(user, body.get("session")))
    return JsonResponse(_public(result), status=ERROR_STATUS.get(result.get("error_kind"), 200))


@_json_login_required
@require_POST
def feedback(request, message_id):
    """👍/👎 on an answer (FR-36). Sending the current rating again clears it."""
    message = get_object_or_404(ChatMessage, pk=message_id, session__user=request.user, role="assistant")
    try:
        value = json.loads(request.body or b"{}").get("value")
    except (json.JSONDecodeError, AttributeError):
        value = None
    if value not in (1, -1):
        return JsonResponse({"status": "error", "message": "Rating must be 1 or -1."}, status=400)
    message.feedback = None if message.feedback == value else value
    message.save(update_fields=["feedback"])
    return JsonResponse({"feedback": message.feedback})


@login_required
@require_POST
def log_problem(request, message_id):
    """Confirm the tutor's suggested "log this problem" action (FR-35)."""
    message = get_object_or_404(ChatMessage, pk=message_id, session__user=request.user, role="assistant")
    if apply_log_problem(message):
        messages.success(request, "Added to this plant's Problem log.")
    else:
        messages.info(request, "This problem is already logged.")
    return redirect(f"{reverse('tutor:ask')}?session={message.session_id}")


@login_required
@require_http_methods(["GET", "POST"])
def diagnose(request):
    """Photo diagnosis form (FR-33)."""
    user = request.user
    status = 200
    if request.method == "POST":
        form = DiagnosisForm(request.POST, request.FILES, user=user)
        if form.is_valid():
            garden = GardenContext(user).find(form.cleaned_data["plant"])
            try:
                diagnosis = run_diagnosis(user, form.cleaned_data["image"], garden, form.cleaned_data["note"])
            except DiagnosisError as exc:
                form.add_error("image", exc.message)
                status = exc.status
            else:
                return redirect("tutor:diagnosis_detail", diagnosis.pk)
        else:
            status = 400
    else:
        form = DiagnosisForm(user=user, initial={"plant": request.GET.get("plant", "")})
    return render(request, "tutor/diagnose.html", {"form": form}, status=status)


@login_required
def diagnosis_detail(request, diagnosis_id):
    diagnosis = get_object_or_404(Diagnosis, pk=diagnosis_id, user=request.user)
    form = SaveDiagnosisForm(user=request.user, initial={"plant": diagnosis.user_plant_id})
    return render(request, "tutor/diagnosis_detail.html", {"diagnosis": diagnosis, "result": diagnosis.result, "form": form})


@login_required
@require_POST
def save_diagnosis(request, diagnosis_id):
    """Save a diagnosis to one of the user's plants (FR-33). The plant choices are limited to their own."""
    diagnosis = get_object_or_404(Diagnosis, pk=diagnosis_id, user=request.user)
    form = SaveDiagnosisForm(request.POST, user=request.user)
    if not form.is_valid() or not diagnosis.result.get("is_plant"):
        messages.error(request, "Please choose one of your plants.")
    else:
        save_to_problem(diagnosis, GardenContext(request.user).find(form.cleaned_data["plant"]))
        messages.success(request, "Saved to this plant's Problem log.")
    return redirect("tutor:diagnosis_detail", diagnosis.pk)
