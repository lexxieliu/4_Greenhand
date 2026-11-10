from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from . import services
from .models import Notification


@login_required
def open_notification(request, notification_id):
    """Mark one notification read and go to what it is about."""
    notification = get_object_or_404(Notification, pk=notification_id, recipient=request.user)
    services.mark_read(request.user, notification.pk)
    return redirect(notification.link_url or "garden:dashboard")


@login_required
@require_POST
def read_all(request):
    services.mark_read(request.user)
    return JsonResponse({"unread": 0})
