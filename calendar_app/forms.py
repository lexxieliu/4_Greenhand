from django import forms

from .models import CalendarEvent, Reminder
from .recurrence import local_to_utc


class ReminderForm(forms.ModelForm):
    start_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))

    frequency = forms.ChoiceField(
        choices=[("", "One time"), ("DAILY", "Daily"), ("WEEKLY", "Weekly")],
        required=False,
    )
    interval = forms.IntegerField(
        min_value=1,
        max_value=365,
        initial=1,
        help_text="Repeat every this many days or weeks.",
    )

    class Meta:
        model = Reminder
        fields = [
            "user_plant",
            "type",
            "title",
            "start_date",
            "time_of_day",
            "timezone",
            "frequency",
            "interval",
            "weather_aware",
        ]
        widgets = {"time_of_day": forms.TimeInput(attrs={"type": "time"})}

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.user = user
        self.fields["user_plant"].queryset = user.my_garden_plants.all()

    def clean(self):
        cleaned = super().clean()
        frequency, interval = cleaned.get("frequency"), cleaned.get("interval")
        self.instance.recurrence_rule = (
            f"FREQ={frequency};INTERVAL={interval}" if frequency and interval else ""
        )
        return cleaned

    def save(self, commit=True):
        reminder = super().save(commit=False)
        reminder.next_due_at = local_to_utc(
            self.cleaned_data["start_date"], reminder.time_of_day, reminder.timezone
        )
        if commit:
            reminder.save()
        return reminder


class CalendarEventForm(forms.ModelForm):
    class Meta:
        model = CalendarEvent
        fields = ["user_plant", "event_type", "title", "date"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.user = user
        self.fields["user_plant"].queryset = user.my_garden_plants.all()

    def save(self, commit=True):
        event = super().save(commit=False)
        event.icon = {
            "watering": "i-drop",
            "planted": "i-sprout",
            "germination": "i-sprout",
            "flowering": "i-sprout",
            "fruiting": "i-basket",
            "harvest": "i-basket",
            "problem": "i-alert",
            "frost_alert": "i-snow",
        }.get(event.event_type, "i-calendar")
        if commit:
            event.save()
        return event
