import json

from django.http import HttpResponse


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

