from django import forms

from .guardrails import MAX_RAW_CHARS


class QuestionForm(forms.Form):
    question = forms.CharField(
        label="Your gardening question",
        max_length=MAX_RAW_CHARS,
        widget=forms.Textarea(attrs={
            "rows": 3,
            "class": "form-control",
            "placeholder": "e.g. Why are my basil leaves turning yellow?",
        }),
    )
