from django.contrib import admin

from .models import CalendarEvent, Reminder, ReminderOccurrence, ReminderOverride

admin.site.register([Reminder, ReminderOccurrence, ReminderOverride, CalendarEvent])
