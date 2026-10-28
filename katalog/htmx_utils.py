import json
from functools import wraps

from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse


def is_htmx(request):
    return request.headers.get("HX-Request") == "true"


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


def login_required_htmx(view):
    """login_required that sends users to SSO UI, also from inside an HTMX swap.

    A plain 302 would make HTMX follow it and paste the login page into the
    modal, so HTMX requests get an HX-Redirect (a full-page navigation) instead.
    """

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated:
            return view(request, *args, **kwargs)
        login_url = f"{reverse('auth_ssoui:login')}?next={request.get_full_path()}"
        if is_htmx(request):
            return hx_redirect(login_url)
        return redirect(login_url)

    return wrapper
