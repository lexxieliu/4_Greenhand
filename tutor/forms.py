from django import forms

from .context import garden_plants
from .guardrails import MAX_RAW_CHARS


class QuestionForm(forms.Form):
    # Not required: an empty question reaches guardrails.check_input, which gives the friendly message.
    question = forms.CharField(
        label="Your gardening question",
        max_length=MAX_RAW_CHARS,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "class": "dash-input", "placeholder": "e.g. Why are the lower leaves on my basil turning yellow?"}),
    )
    plant = forms.ChoiceField(label="About", required=False, widget=forms.Select(attrs={"class": "dash-input"}))

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plant"].choices = [("", "My whole garden (auto-detect the plant)")] + [
            (p["id"], p["nickname"]) for p in garden_plants(user)
        ]
