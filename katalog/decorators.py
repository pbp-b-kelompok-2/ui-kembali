import json
from functools import wraps

from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .models import Item


def is_htmx(request) -> bool:
    return request.headers.get("HX-Request") == "true"


def toast_response(msg, level="info", status=200, **extra):
    """An empty response whose HX-Trigger header makes toast.js show `msg`."""
    response = HttpResponse(status=status)
    response["HX-Trigger"] = json.dumps({"toast": {"msg": msg, "level": level, **extra}})
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
            response = HttpResponse(status=204)
            response["HX-Redirect"] = login_url
            return response
        return redirect(login_url)

    return wrapper


def owner_required(include_deleted=False):
    """Load the Item from the URL's `pk` and let only its owner through.

    Missing item → 404. Someone else's item → 403: an error toast for HTMX,
    the 403 page otherwise. The view receives `item` instead of `pk`.
    """
    manager = Item.all_objects if include_deleted else Item.objects

    def decorator(view):
        @wraps(view)
        @login_required_htmx
        def wrapper(request, pk, *args, **kwargs):
            item = get_object_or_404(manager, pk=pk)
            if item.owner_id != request.user.id:
                if is_htmx(request):
                    return toast_response(
                        "Bukan barangmu, aksi ditolak.", "error", status=403
                    )
                return render(request, "katalog/403.html", status=403)
            return view(request, item, *args, **kwargs)

        return wrapper

    return decorator
