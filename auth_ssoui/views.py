from django.shortcuts import render, redirect
from django.urls import reverse
from .sso_compat import with_sso_ui, get_service_url, get_cas_client
from django.http import JsonResponse, HttpResponse
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from .models import *
from .forms import *
import json

# Create your views here.
@with_sso_ui()
def login_sso(request, sso_profile):
    username = sso_profile["username"]
    attrs = sso_profile["attributes"]

    user, created = get_user_model().objects.get_or_create(username=sso_profile["username"])
    if created:
        user.set_unusable_password()
        user.save()

    Profile.objects.update_or_create(
        user=user,
        defaults={
            "nama": attrs.get("nama", ""),
            "peran": "Mahasiswa",
            "faculty": attrs.get("faculty", ""),
        },
    )

    login(request, user)

    if not user.profile.is_complete:
        return redirect("auth_ssoui:lengkapi_profil")
    return redirect("main:lobby")   # ganti sesuai nama url kamu

def logout_sso(request):
    logout(request)

    service_url = get_service_url(request)
    client = get_cas_client(service_url)
    return redirect(client.get_logout_url(request.build_absolute_uri(reverse("main:lobby"))))

@login_required(login_url="/auth/login/")
def lengkapi_profil(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.is_complete = True
            profile.save()
            return redirect("main:lobby")
    else:
        form = ProfileForm(instance=profile)

    return render(request, "form_user.html", {"form": form})

@with_sso_ui()
def get_login_cred(request, sso_profile):
    print(json.dumps(sso_profile, indent=2, ensure_ascii=False))
    return JsonResponse(sso_profile)