from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from .sso_compat import with_sso_ui, get_service_url, get_cas_client
from django.http import JsonResponse, HttpResponse
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from .models import *
from .forms import *
from .decorators import *
import json

# Create your views here.
def with_toast(response, msg, level="success"):
    response["HX-Trigger"] = json.dumps({"toast": {"msg": msg, "level": level}})
    return response

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

    if request.user.profile.is_complete:
        if request.headers.get("HX-Request"):
            response = HttpResponse(status=204)
            response["HX-Redirect"] = reverse("auth_ssoui:profile")
            return response
        return redirect("auth_ssoui:profile")

    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.peran = "Mahasiswa"
            profile.is_complete = True
            profile.save()
            if request.headers.get("HX-Request"):
                response = HttpResponse(status=204)
                response["HX-Trigger"] = json.dumps({
                    "toast": {"msg": "Profil berhasil dilengkapi", "level": "success"},
                    "redirectLater": {"url": reverse("main:lobby"), "delay": 1200},
                })
                return response
            return redirect("main:lobby")
        response = render(request, "components/profile_form_modal.html",
                          {"form": form, "profile": profile})
        return with_toast(response, "Ada isian yang belum benar, cek lagi ya", "error")
    else:
        form = ProfileForm(instance=profile)
    context = {
        "form" : form,
        "profile" : profile,
    }
    return render(request, "form_user.html", context)

@with_sso_ui()
def get_login_cred(request, sso_profile):
    print(json.dumps(sso_profile, indent=2, ensure_ascii=False))
    return JsonResponse(sso_profile)

@profile_required
def profile_page(request):
    profile = get_object_or_404(Profile, user=request.user)
    context = {
        "profile" : profile,
    }
    return render(request, "profile.html", context)