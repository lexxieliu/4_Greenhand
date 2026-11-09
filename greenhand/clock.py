"""The app's notion of "today".

The preview still shows mock weather written relative to mock_data.TODAY (Oct 13, 2026), so the
garden uses the same date to keep "days since planting", reminders and frost alerts consistent.
When live weather lands (Area 3), return timezone.localdate() here instead.
"""
from django.utils import timezone

from greenhand import mock_data


def today():
    return mock_data.TODAY


def now():
    """The current time on the app's "today", so timestamps (resolved, first harvest …) match the dates
    the garden shows. Equal to timezone.now() once today() returns the real date."""
    return timezone.now() + (today() - timezone.localdate())
