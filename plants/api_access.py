from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.http import JsonResponse


def api_login_required(view_func):
    """Protect a JSON endpoint.

    - Logged-in users: the view runs normally.
    - Browsers (Accept: text/html): redirected to the login page.
    - API clients (scripts, curl, fetch): get a 401 with a JSON body
      instead of an HTML login page.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)

        wants_html = "text/html" in request.headers.get("Accept", "")
        if wants_html and request.GET.get("format") != "json":
            return redirect_to_login(request.get_full_path())
        return JsonResponse({"error": "Authentication required"}, status=401)

    return wrapper


def public_api(view_func):
    """Mark an endpoint as the one public API.

    Adds a CORS header so tools served from another origin (the Vega-Lite
    editor at vega.github.io, Observable, etc.) are allowed to fetch it.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        response = view_func(request, *args, **kwargs)
        response["Access-Control-Allow-Origin"] = "*"
        return response

    return wrapper