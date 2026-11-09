from zoneinfo import ZoneInfo

from django.utils import timezone

from .models import NotificationPreference


class UserTimezoneMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        zone = "UTC"
        if request.user.is_authenticated:
            zone = (
                NotificationPreference.objects.filter(user=request.user)
                .values_list("timezone", flat=True)
                .first()
                or zone
            )
        with timezone.override(ZoneInfo(zone)):
            return self.get_response(request)
