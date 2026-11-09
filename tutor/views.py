import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods, require_POST

from .forms import QuestionForm
from .models import AITutorLog
from .services import ask_tutor

HISTORY_SIZE = 6
ERROR_STATUS = {"invalid_input": 400, "rate_limited": 429, "invalid_output": 502, "unavailable": 503, "timeout": 504}


def _public(result):
    """Drop the raw model text before a result leaves the server."""
    return {k: v for k, v in result.items() if k != "raw"}


def _history(user):
    items = []
    for log in AITutorLog.objects.filter(user=user)[:HISTORY_SIZE]:
        try:
            result = json.loads(log.answer)
        except json.JSONDecodeError:
            result = {"status": "answer", "answer": log.answer}
        items.append({"log": log, "result": result})
    return items


@login_required
@require_http_methods(["GET", "POST"])
def ask(request):
    """AI Gardening Tutor page (FR-30/32): question + optional plant scope -> grounded answer."""
    user = request.user
    result = None
    if request.method == "POST":
        form = QuestionForm(request.POST)
        if form.is_valid():
            result = ask_tutor(form.cleaned_data["question"], form.cleaned_data["plant"], user=user, rate_key=user.pk)
    else:
        form = QuestionForm(initial={"question": request.GET.get("q", ""), "plant": request.GET.get("plant", "")})
    return render(request, "tutor/ask.html", {"form": form, "result": result, "history": _history(user)})


@require_POST
def api_ask(request):
    """JSON endpoint for the dashboard chat and the My Garden drawer: {"question", "plant"} -> result."""
    if not request.user.is_authenticated:  # a script call gets JSON, not a redirect to the login page
        return JsonResponse({"status": "error", "error_kind": "unauthenticated", "message": "Sign in to ask the tutor."}, status=401)
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "error_kind": "invalid_input", "message": "Invalid request."}, status=400)
    if not isinstance(body, dict):
        return JsonResponse({"status": "error", "error_kind": "invalid_input", "message": "Invalid request."}, status=400)
    user = request.user
    result = ask_tutor(body.get("question"), str(body.get("plant") or ""), user=user, rate_key=user.pk)
    return JsonResponse(_public(result), status=ERROR_STATUS.get(result.get("error_kind"), 200))
