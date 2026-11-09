"""Input validation for the My Garden endpoints. Field names match the dialog inputs in
templates/garden/my_garden.html and the Start Growing form on the plant page."""
from datetime import timedelta

from django import forms

from greenhand.clock import today
from plants.selectors import published_plants

from .images import clean_photo
from .models import CareLog, Harvest, Problem, Reminder, TimelineEntry, UserPlant

MAX_PAST_DAYS = 5 * 365      # a plant can't have been planted more than 5 years ago
MAX_PLAN_DAYS = 365          # or be planned more than a year ahead


class PhotoMixin:
    """Optional `photo` upload, validated and stripped of EXIF by garden.images.clean_photo."""

    def clean_photo(self):
        upload = self.cleaned_data.get("photo")
        return clean_photo(upload) if upload else None


def _not_in_future(value):
    if value > today():
        raise forms.ValidationError("That date is in the future.")
    return value


class StartGrowingForm(forms.Form):
    plant = forms.ModelChoiceField(queryset=published_plants(), to_field_name="slug",
                                   error_messages={"invalid_choice": "Pick a plant from the catalog."})
    nickname = forms.CharField(max_length=60, required=False)
    planted_on = forms.DateField(error_messages={"invalid": "Please choose a valid planting date."})
    start_method = forms.ChoiceField(choices=UserPlant.StartMethod.choices)
    setting = forms.ChoiceField(choices=UserPlant.Setting.choices)
    container = forms.CharField(max_length=50, required=False)
    quantity = forms.IntegerField(min_value=1, max_value=999, required=False)

    def clean_planted_on(self):
        value = self.cleaned_data["planted_on"]
        if value < today() - timedelta(days=MAX_PAST_DAYS) or value > today() + timedelta(days=MAX_PLAN_DAYS):
            raise forms.ValidationError("Pick a date within the last 5 years or the next 12 months.")
        return value


class TimelineForm(PhotoMixin, forms.Form):
    stage = forms.ChoiceField(choices=TimelineEntry.Stage.choices)
    date = forms.DateField()
    note = forms.CharField(max_length=1000, required=False)
    photo = forms.FileField(required=False)
    update_status = forms.BooleanField(required=False)

    def clean_date(self):
        return _not_in_future(self.cleaned_data["date"])


class CareLogForm(forms.Form):
    action = forms.ChoiceField(choices=CareLog.Action.choices)
    date = forms.DateField()
    amount = forms.CharField(max_length=50, required=False)
    note = forms.CharField(max_length=1000, required=False)

    def clean_date(self):
        return _not_in_future(self.cleaned_data["date"])


class ProblemForm(PhotoMixin, forms.Form):
    title = forms.CharField(max_length=120)
    description = forms.CharField(max_length=2000, required=False)
    category = forms.ChoiceField(choices=Problem.Category.choices)
    severity = forms.ChoiceField(choices=Problem.Severity.choices)
    photo = forms.FileField(required=False)


class ProblemStatusForm(forms.Form):
    status = forms.ChoiceField(choices=Problem.Status.choices)
    resolution_note = forms.CharField(max_length=1000, required=False)


class HarvestForm(PhotoMixin, forms.Form):
    date = forms.DateField()
    quantity = forms.DecimalField(min_value=0, max_digits=8, decimal_places=2, required=False)
    unit = forms.ChoiceField(choices=Harvest.Unit.choices)
    note = forms.CharField(max_length=1000, required=False)
    photo = forms.FileField(required=False)
    final = forms.BooleanField(required=False)

    def clean_date(self):
        return _not_in_future(self.cleaned_data["date"])


class StatusForm(forms.Form):
    status = forms.ChoiceField(choices=UserPlant.Status.choices)
    failure_reason = forms.ChoiceField(choices=UserPlant.FailureReason.choices, required=False)


class ReminderForm(forms.Form):
    type = forms.ChoiceField(choices=Reminder.Type.choices)
    every = forms.IntegerField(min_value=0, max_value=90)
    time = forms.TimeField(required=False)


class ReminderFlagForm(forms.Form):
    flag = forms.ChoiceField(choices=[(f, f) for f in ("active", "inapp", "email", "weather_aware")])
    value = forms.BooleanField(required=False)
