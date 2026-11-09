import calendar
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from garden.models import Garden
from notifications.models import NotificationPreference

from .forms import CalendarEventForm, ReminderForm
from .models import CalendarEvent, Reminder, ReminderOccurrence
from .services import act_on_occurrence, materialize


@login_required
def month_view(request):
    pref, _ = NotificationPreference.objects.get_or_create(user=request.user)
    today = timezone.now().astimezone(ZoneInfo(pref.timezone)).date()
    try:
        month = date.fromisoformat(
            request.GET.get("month", today.strftime("%Y-%m")) + "-01"
        )
        if not 1900 <= month.year <= 2100:
            raise ValueError
    except ValueError:
        return HttpResponseBadRequest("Use a month between 1900-01 and 2100-12.")
    end = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
    selected = request.GET.get("plant", "")
    plants = Garden.objects.filter(user=request.user).select_related("plant")
    if selected:
        try:
            selected = int(selected)
        except ValueError:
            raise Http404
        get_object_or_404(plants, pk=selected)
    events = CalendarEvent.objects.filter(
        user=request.user, date__gte=month, date__lt=end
    )
    if selected:
        events = events.filter(user_plant_id=selected)
    grouped = {}
    for event in events.order_by("date", "pk"):
        grouped.setdefault(event.date, []).append(event)
    from .selectors import projected_events

    for event in projected_events(request.user, month, end, selected):
        grouped.setdefault(event["date"], []).append(event)
    weeks = [
        [
            {
                "date": day,
                "in_month": day.month == month.month,
                "events": grouped.get(day, []),
            }
            for day in week
        ]
        for week in calendar.Calendar().monthdatescalendar(month.year, month.month)
    ]
    occurrences = (
        ReminderOccurrence.objects.filter(
            reminder__user=request.user, due_at__gte=timezone.now() - timedelta(days=7)
        )
        .select_related("reminder")
        .order_by("due_at")
    )
    if selected:
        occurrences = occurrences.filter(reminder__user_plant_id=selected)
    return render(
        request,
        "calendar_app/month.html",
        {
            "weeks": weeks,
            "month": month,
            "previous": (month - timedelta(days=1)).strftime("%Y-%m"),
            "next": end.strftime("%Y-%m"),
            "plants": plants,
            "selected": selected,
            "occurrences": occurrences[:100],
            "reminders": Reminder.objects.filter(user=request.user, is_active=True),
        },
    )


@login_required
def create_reminder(request):
    pref, _ = NotificationPreference.objects.get_or_create(user=request.user)
    form = ReminderForm(
        request.POST or None,
        user=request.user,
        initial={"timezone": pref.timezone, "start_date": timezone.localdate()},
    )
    if request.method == "POST" and form.is_valid():
        reminder = form.save()
        materialize(reminder, timezone.now() + timedelta(days=62))
        return redirect("calendar_app:month")
    return render(request, "calendar_app/form.html", {"form": form})


@login_required
@require_POST
def occurrence_action(request, pk):
    get_object_or_404(ReminderOccurrence, pk=pk, reminder__user=request.user)
    action = request.POST.get("action")
    if action not in ("done", "skip", "override"):
        return HttpResponseBadRequest("Unknown action")
    act_on_occurrence(request.user, pk, action, request.POST.get("reason", ""))
    return redirect("calendar_app:month")


@login_required
@require_POST
def pause_reminder(request, pk):
    reminder = get_object_or_404(Reminder, pk=pk, user=request.user)
    reminder.is_active = False
    reminder.save(update_fields=["is_active"])
    future = reminder.occurrences.filter(status="pending", due_at__gt=timezone.now())
    CalendarEvent.objects.filter(
        source_type="reminder", source_id__in=future.values("pk")
    ).delete()
    future.update(status="skipped_user", skip_reason="Reminder paused")
    return redirect("calendar_app:month")


@login_required
def create_event(request):
    form = CalendarEventForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("calendar_app:month")
    return render(request, "calendar_app/form.html", {"form": form, "event_form": True})
