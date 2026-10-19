import json

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from . import llm
from .forms import QuestionForm
from .guardrails import check_input, rate_limited
from .models import AITutorLog

HISTORY_SIZE = 10
RATE_LIMIT_MESSAGE = "You have reached the hourly limit for AI questions. Please try again later."
UNAVAILABLE_MESSAGE = "The AI tutor is unavailable right now. Please try again in a moment."


def _history(user):
    """The user's latest answers, with the stored JSON turned back into dicts for the template."""
    items = []
    for log in AITutorLog.objects.filter(user=user)[:HISTORY_SIZE]:
        try:
            data = json.loads(log.answer)
        except json.JSONDecodeError:
            data = {"answer": log.answer}
        items.append({"log": log, "data": data})
    return items


@login_required
def ask(request):
    """AI Gardening Tutor: clean/check the question, ask the local model, validate, save, show."""
    form = QuestionForm(request.POST or None)
    result = None
    error = None

    if request.method == "POST" and form.is_valid():
        question = form.cleaned_data["question"].strip()
        ok, reason = check_input(question)
        if not ok:
            error = reason
        elif rate_limited(request.user.id):
            error = RATE_LIMIT_MESSAGE
        else:
            try:
                result, raw = llm.generate("care", question)
            except llm.LLMUnavailable:
                error = UNAVAILABLE_MESSAGE
            else:
                if result.get("error"):                 # model output was not usable JSON
                    error = result["message"]
                    result = None
                else:                                   # answer or refusal: keep a record of both
                    AITutorLog.objects.create(
                        user=request.user,
                        question=question,
                        answer=json.dumps(result),
                        thinking_process=raw,
                    )
                    form = QuestionForm()               # clear the box after a successful answer

    return render(request, "tutor/ask.html", {
        "form": form,
        "result": result,
        "error": error,
        "history": _history(request.user),
    })
