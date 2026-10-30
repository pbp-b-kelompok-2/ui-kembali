import json
from functools import wraps

from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse


def is_htmx(request):
    return request.headers.get("HX-Request") == "true"


def login_required_htmx(view):
    """Redirect anonymous requests to login, including full-page HTMX navigation."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated:
            return view(request, *args, **kwargs)
        login_url = f"{reverse('auth_ssoui:login')}?next={request.get_full_path()}"
        if is_htmx(request):
            return hx_redirect(login_url)
        return redirect(login_url)

    return wrapper


def add_toast(response, msg, level="success", **extra):
    """Make toast.js show `msg` once HTMX receives `response` (HX-Trigger header)."""
    response["HX-Trigger"] = json.dumps({"toast": {"msg": msg, "level": level, **extra}})
    return response


def toast_only(msg, level="error", status=200, **extra):
    """An empty response that only shows a toast (errors, deletes)."""
    return add_toast(HttpResponse(status=status), msg, level, **extra)


def hx_redirect(url):
    """Tell HTMX to load `url` as a full page (instead of swapping a partial)."""
    response = HttpResponse(status=204)
    response["HX-Redirect"] = url
    return response

