"""Who the current request acts for."""
from django.contrib.auth.models import User

from greenhand import mock_data

DEMO_USERNAME = mock_data.USER["username"]


def current_user(request):
    """The signed-in user, or the demo account (balcony_maya) while login is not wired up yet.
    Every garden query is filtered by this user, so one account never sees another's plants."""
    if request.user.is_authenticated:
        return request.user
    return User.objects.get_or_create(username=DEMO_USERNAME)[0]
