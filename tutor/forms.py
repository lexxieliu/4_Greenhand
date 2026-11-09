from django import forms

from .context import GardenContext
from .guardrails import MAX_RAW_CHARS


def _plant_choices(user):
    return [(str(p.pk), p.label) for p in GardenContext(user).plants()]


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
        self.fields["plant"].choices = [("", "My whole garden (auto-detect the plant)")] + _plant_choices(user)


class DiagnosisForm(forms.Form):
    image = forms.FileField(label="Photo of the plant", widget=forms.ClearableFileInput(
        attrs={"accept": "image/jpeg,image/png,image/webp", "class": "dash-input"}))
    plant = forms.ChoiceField(label="Which plant?", required=False, widget=forms.Select(attrs={"class": "dash-input"}))
    note = forms.CharField(label="Anything else to know? (optional)", required=False, max_length=300,
                           widget=forms.TextInput(attrs={"class": "dash-input", "placeholder": "e.g. Started after last week's rain"}))

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plant"].choices = [("", "Not sure / not in my garden")] + _plant_choices(user)


class SaveDiagnosisForm(forms.Form):
    plant = forms.ChoiceField(label="Save to", widget=forms.Select(attrs={"class": "dash-input"}))

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plant"].choices = _plant_choices(user)
