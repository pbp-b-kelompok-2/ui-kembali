import json

from django.db.models import Q
from django.db.models.fields import related_descriptors
from asyncio import proactor_events
from django.core.files import uploadedfile
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.http import JsonResponse, HttpResponse
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator

from .sso_compat import with_sso_ui, get_service_url, get_cas_client
from .models import *
from .forms import *
from .decorators import *

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
            "angkatan" : "20" + attrs.get("npm", "")[:2]
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

FILL_FIELDS = ["nama", "angkatan", "nama_panggilan", "no_hp", "faculty", "pfp", "titik_favorit", "bio"]

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
        form = ProfileForm(request.POST, request.FILES, fields=FILL_FIELDS, instance=profile)
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
        response = render(request, "profile/components/profile_form_modal.html",
                          {"form": form, "profile": profile})
        return with_toast(response, "Ada isian yang belum benar, cek lagi ya", "error")
    else:
        form = ProfileForm(fields=FILL_FIELDS, instance=profile)
    context = {
        "form" : form,
        "profile" : profile,
        "form_action" : reverse("auth_ssoui:lengkapi_profil"),
    }
    return render(request, "profile/first_user.html", context)

@with_sso_ui()
def get_login_cred(request, sso_profile):
    print(json.dumps(sso_profile, indent=2, ensure_ascii=False))
    return JsonResponse(sso_profile)

EDIT_FIELDS = ["nama_panggilan", "pfp", "no_hp", "titik_favorit", "bio"]

@profile_required
def edit_profil(request):
    profile = get_object_or_404(Profile, user=request.user)

    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, fields=EDIT_FIELDS, instance=profile)
        
        if form.is_valid():
            form.save()
            context = {
                "form": ProfileForm(fields=EDIT_FIELDS, instance=profile),
                "profile": profile,
                "form_action": reverse("auth_ssoui:edit_profil"),
                "oob_pfp": True
            }
            
            if request.headers.get("HX-Request"):
                response = render(request, "profile/components/profile_form_modal.html", context)
                return with_toast(response, "Perubahan profil berhasil disimpan", "success")
            return redirect("auth_ssoui:profile")
        
        response = render(request, "profile/components/profile_form_modal.html",
                          {"form": form, "profile": profile,
                           "form_action": reverse("auth_ssoui:edit_profil")})
        return with_toast(response, "Ada isian yang belum benar, cek lagi ya", "error")

    form = ProfileForm(fields=EDIT_FIELDS, instance=profile)
    return render(request, "profile/components/profile_form_modal.html",
                  {"form": form, "profile": profile,
                   "form_action": reverse("auth_ssoui:edit_profil")})

@profile_required
def profile_page(request):
    from katalog.models import ItemRequest

    field = EDIT_FIELDS
    profile = get_object_or_404(Profile, user=request.user)
    form = ProfileForm(fields=field, instance=profile)

    # Ambil riwayat transaksi dari dua sisi:
    # 1) Sebagai requester (barang yang dia minta/beli/adopsi)
    # 2) Sebagai owner item (barang yang dia jual/berikan ke orang lain)
    # Ambil 5 terbaru (FIFO: antrian diproses dari yang paling lama)
    riwayat_terbaru = (
        ItemRequest.objects.filter(
            Q(requester=request.user) | Q(item__owner=request.user)
        )
        .select_related("item", "item__owner", "requester")
        .order_by("-created_at")[:3]
    )

    context = {
        "form": form,
        "profile": profile,
        "form_action": reverse("auth_ssoui:edit_profil"),
        "riwayat_terbaru": riwayat_terbaru,
    }
    return render(request, "profile/profile.html", context)


@profile_required
def profile_history(request):
    """Return the paginated history partial requested by the profile page."""
    from katalog.models import ItemRequest

    riwayat = (
        ItemRequest.objects.filter(
            Q(requester=request.user) | Q(item__owner=request.user)
        )
        .select_related("item", "item__owner", "requester")
        .order_by("-created_at")
    )
    page_obj = Paginator(riwayat, 5).get_page(request.GET.get("page"))

    return render(
        request,
        "profile/components/full_riwayat.html",
        {"page_obj": page_obj},
    )
