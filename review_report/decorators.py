from functools import wraps
from urllib.parse import urlencode
from django.shortcuts import redirect
from django.urls import reverse
from katalog.htmx_utils import hx_redirect, is_htmx


def login_required_htmx(view):
    """Use a full-page redirect when an HTMX session expires."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.user.is_authenticated:
            return view(request, *args, **kwargs)
        url = reverse('auth_ssoui:login') + '?' + urlencode({'next': request.get_full_path()})
        return hx_redirect(url) if is_htmx(request) else redirect(url)
    return wrapped
