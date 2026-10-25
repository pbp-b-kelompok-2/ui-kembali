"""
Drop-in replacements for django_sso_ui.decorators and django_sso_ui.utils
that work on Django 3.0+ (no django.utils.six dependency).
"""

import os
import json
from urllib.parse import urlunparse

from cas import CASClient
from django.conf import settings as django_settings
from django.http import HttpResponseRedirect


# ---------------------------------------------------------------------------
# Utility helpers (replacements for django_sso_ui.utils)
# ---------------------------------------------------------------------------

def normalize_username(username):
    return username.lower()


def get_protocol(request):
    force_https = getattr(django_settings, "SSO_UI_FORCE_SERVICE_HTTPS", False)
    if request.is_secure() or force_https:
        return "https"
    return "http"


def get_service_url(request, redirect_to=None):
    protocol = get_protocol(request)
    host = request.get_host()
    return urlunparse((protocol, host, request.path, "", "", ""))


def get_cas_client(service_url=None, request=None):
    import requests as req_lib
    server_url = django_settings.SSO_UI_URL
    if server_url and request and server_url.startswith("/"):
        scheme = request.META.get("X-Forwarded-Proto", request.scheme)
        server_url = scheme + "://" + request.META["HTTP_HOST"] + server_url

    session = req_lib.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; UIKembali/1.0)",
    })
    return CASClient(service_url=service_url, server_url=server_url, version=2, session=session)


def get_additional_info(kd_org):
    path = os.path.dirname(os.path.abspath(__file__))
    # The additional-info.json lives inside the django_sso_ui package
    import django_sso_ui
    pkg_dir = os.path.dirname(os.path.abspath(django_sso_ui.__file__))
    filename = os.path.join(pkg_dir, "additional-info.json")

    with open(filename, "r") as fd:
        as_json = json.load(fd)
        if kd_org in as_json:
            return as_json[kd_org]
    return None


def authenticate(ticket, client):
    import logging
    from urllib.parse import urljoin, urlencode
    logger = logging.getLogger(__name__)

    # Log the exact URL being sent to help debug 400 errors
    validate_url = urljoin(client.server_url, client.url_suffix)
    debug_params = urlencode({"ticket": ticket, "service": client.service_url})
    logger.warning("CAS validate URL: %s?%s", validate_url, debug_params)

    try:
        username, attributes, _ = client.verify_ticket(ticket)
    except Exception as exc:
        # The CAS server may return HTML instead of XML
        # (e.g. when the service URL is not registered).
        # Log the raw response for debugging and fail gracefully.
        logger.error("CAS ticket verification failed: %s", exc)

        # Try to capture the raw response for diagnosis
        try:
            raw = client.get_verification_response(ticket)
            logger.error("Raw CAS response:\n%s", raw.decode("utf-8", errors="replace")[:2000])
        except Exception:
            pass

        return None

    if not username:
        return None

    if "kd_org" in attributes:
        attributes.update(get_additional_info(attributes["kd_org"]) or {})

    sso_profile = {"username": username, "attributes": attributes}
    return sso_profile


# ---------------------------------------------------------------------------
# Decorator (replacement for django_sso_ui.decorators.with_sso_ui)
# ---------------------------------------------------------------------------

def with_sso_ui(force_login=True):
    def decorator(func):
        def wrapper(request, *args, **kwargs):
            service_url = get_service_url(request)
            client = get_cas_client(service_url)
            login_url = client.get_login_url()

            ticket = request.GET.get("ticket")
            if ticket:
                sso_profile = authenticate(ticket, client)

                if sso_profile is None and force_login:
                    return HttpResponseRedirect(login_url)

                kwargs["sso_profile"] = sso_profile
                return func(request, *args, **kwargs)
            else:
                return HttpResponseRedirect(login_url)

        return wrapper

    return decorator

