"""The app's notion of "today" and "now".

Live weather (Area 3) works in real time, so the garden does too. Kept as one place to change if the
app ever needs a fixed demo date again (tests can patch these functions).
"""
from django.utils import timezone


def today():
    return timezone.localdate()


def now():
    return timezone.now()
