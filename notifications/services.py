import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core import signing
from django.core.mail import EmailMessage
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .models import Notification, NotificationPreference

logger = logging.getLogger(__name__)


def notify(
    *,
    recipient,
    key,
    title,
    body,
    kind="reminder",
    plant=None,
    priority=1,
    link="/calendar/",
):
    return Notification.objects.get_or_create(
        dedupe_key=key,
        defaults=dict(
            recipient=recipient,
            user_plant=plant,
            type=kind,
            title=title[:120],
            body=body,
            priority=priority,
            link_url=link,
        ),
    )[0]


def in_quiet_hours(preference, now):
    clock = now.astimezone(ZoneInfo(preference.timezone)).time().replace(tzinfo=None)
    start, end = preference.quiet_start, preference.quiet_end
    if start == end:
        return False
    return start <= clock < end if start < end else clock >= start or clock < end


def stop_token(user_id, plant_id=None, category="reminder"):
    return signing.dumps(
        {"user": user_id, "plant": plant_id, "category": category},
        salt="notification-stop",
    )


def stop_url(user_id, plant_id=None, category="reminder"):
    return settings.SITE_URL.rstrip("/") + reverse(
        "notifications:unsubscribe", args=[stop_token(user_id, plant_id, category)]
    )


def deliver_emails(now=None):
    now = now or timezone.now()
    sent = 0
    for user_id in (
        Notification.objects.filter(emailed_at__isnull=True, recipient__is_active=True)
        .order_by()
        .values_list("recipient_id", flat=True)
        .distinct()
    ):
        NotificationPreference.objects.get_or_create(user_id=user_id)
        # Locks serialize delivery and daily-cap accounting per recipient on PostgreSQL.
        with transaction.atomic():
            pref = (
                NotificationPreference.objects.select_for_update()
                .select_related("user")
                .get(user_id=user_id)
            )
            if not pref.user.email:
                continue
            tz = ZoneInfo(pref.timezone)
            day = now.astimezone(tz).date()
            start = datetime.combine(day, time.min, tzinfo=tz)
            end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz)
            count = Notification.objects.filter(
                recipient_id=user_id, emailed_at__gte=start, emailed_at__lt=end
            ).count()
            pending = Notification.objects.filter(
                recipient_id=user_id, emailed_at__isnull=True
            ).order_by("priority", "created_at")
            for notification in pending:
                if count >= 3:
                    break
                if (
                    notification.type == "reminder"
                    and notification.dedupe_key.startswith(("reminder:", "override:"))
                ):
                    from calendar_app.models import ReminderOccurrence

                    occurrence_id = notification.dedupe_key.partition(":")[2]
                    if not ReminderOccurrence.objects.filter(
                        pk=occurrence_id, status__in=["pending", "sent"]
                    ).exists():
                        continue
                frost = (
                    notification.type == "weather_alert" and notification.priority == 0
                )
                allowed = (
                    (frost and pref.frost_email)
                    or (notification.type == "reminder" and pref.reminder_email)
                    or (notification.type == "digest" and pref.digest_email)
                )
                if not allowed or (in_quiet_hours(pref, now) and not frost):
                    continue
                if (
                    notification.user_plant_id
                    and pref.suppressed_plants.filter(
                        pk=notification.user_plant_id
                    ).exists()
                ):
                    continue
                category = "digest" if notification.type == "digest" else "reminder"
                url = stop_url(user_id, category=category)
                body = (
                    notification.body
                    + "\n\n"
                    + settings.SITE_URL.rstrip("/")
                    + notification.link_url
                )
                body += "\n\nStop these emails: " + url
                if notification.user_plant_id:
                    body += "\nStop reminders for this plant: " + stop_url(
                        user_id, notification.user_plant_id
                    )
                headers = {}
                if notification.type == "digest":
                    if not settings.EMAIL_POSTAL_ADDRESS:
                        continue
                    body += "\n" + settings.EMAIL_POSTAL_ADDRESS
                    headers = {
                        "List-Unsubscribe": "<" + url + ">",
                        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
                    }
                try:
                    delivered = EmailMessage(
                        notification.title,
                        body,
                        settings.DEFAULT_FROM_EMAIL,
                        [pref.user.email],
                        headers=headers,
                    ).send()
                    if not delivered:
                        raise OSError("Email backend did not accept the message")
                except Exception as exc:
                    notification.email_error = str(exc)[:1000]
                    notification.save(update_fields=["email_error"])
                    logger.warning(
                        "Email delivery failed for notification %s", notification.pk
                    )
                    continue
                notification.emailed_at = now
                notification.email_error = ""
                notification.save(update_fields=["emailed_at", "email_error"])
                sent += 1
                count += 1
    return sent


def weekly_digest(now=None):
    from calendar_app.models import ReminderOccurrence

    now = now or timezone.now()
    for pref in NotificationPreference.objects.filter(
        digest_email=True, user__is_active=True
    ).select_related("user"):
        local = now.astimezone(ZoneInfo(pref.timezone))
        week = local.date() - timedelta(days=local.weekday())
        done = ReminderOccurrence.objects.filter(
            reminder__user=pref.user, completed_at__gte=now - timedelta(days=7)
        ).count()
        upcoming = ReminderOccurrence.objects.filter(
            reminder__user=pref.user,
            due_at__gte=now,
            due_at__lt=now + timedelta(days=7),
            status="pending",
        ).count()
        notify(
            recipient=pref.user,
            key=f"digest:{pref.user_id}:{week}",
            title="Your weekly garden digest",
            body=f"You completed {done} care tasks this week. {upcoming} scheduled tasks are coming up.",
            kind="digest",
            priority=3,
        )
