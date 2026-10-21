from django.shortcuts import render, redirect
from django.urls import reverse
from django_sso_ui.decorators import with_sso_ui
from django_sso_ui.utils import get_service_url, get_cas_client
from django.http import JsonResponse, HttpResponse
from django.contrib.auth import get_user_model, login, logout
from .models import *
import json

# Create your views here.
@with_sso_ui()
def login_sso(request, sso_profile):
    username = sso_profile["username"]
    attrs = sso_profile["attributes"]

    user, created = get_user_model().objects.get_or_create(username=username)
    if created:
        user.set_unusable_password()   # login hanya lewat SSO
        user.save()

    Profile.objects.update_or_create(
        user=user,
        defaults={
            "nama": attrs.get("nama", ""),
            "peran": "Mahasiswa",
        },
    )

    login(request, user)
    return redirect("main:lobby")   # ganti sesuai nama url kamu

def logout_sso(request):
    logout(request)

    service_url = get_service_url(request)
    client = get_cas_client(service_url)
    return redirect(client.get_logout_url(request.build_absolute_uri(reverse("main:lobby"))))

@with_sso_ui()
def get_login_cred(request, sso_profile):
    print(json.dumps(sso_profile, indent=2, ensure_ascii=False))
    return JsonResponse(sso_profile)