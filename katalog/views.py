from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import strip_tags
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from . import geocoding
from .filters import RADIUS_CHOICES, filter_items
from .forms import ItemForm
from .htmx_utils import add_toast, hx_redirect, is_htmx, toast_only
from .models import Item, ItemRequest

PAGE_SIZE = 12
LOGIN_URL = "/auth/login/"
TOO_FAST = "Terlalu banyak aksi dalam semenit. Coba lagi sebentar."
NOT_ON_MAP = "Tersimpan, tapi lokasinya belum ketemu di peta. Coba nama tempat yang lebih umum."

PENDING = ItemRequest.Status.PENDING
DITERIMA = ItemRequest.Status.DITERIMA
DITOLAK = ItemRequest.Status.DITOLAK


# --- Catalog (read) -----------------------------------------------------------


def catalog_page(request):
    form, items = filter_items(request.GET)
    # get_page() turns a bad or too-large ?page= into the first/last page.
    page_obj = Paginator(items, PAGE_SIZE).get_page(request.GET.get("page"))
    # Page links keep every filter but replace ?page=.
    params = request.GET.copy()
    params.pop("page", None)
    context = {
        "form": form,
        "page_obj": page_obj,
        "chips": form.active_chips(),
        "querystring": params.urlencode(),
        "radius_choices": RADIUS_CHOICES,
    }
    # The filter form hx-gets this same URL and only wants the grid back.
    # HTMX history restore (after hx-push-url) needs the whole page though.
    if is_htmx(request) and not request.headers.get("HX-History-Restore-Request"):
        return render(request, "katalog/_item_grid.html", context)
    return render(request, "katalog/catalog.html", context)


def _public_coords(item, exact):
    """Exact point for logged-in users; anonymous users only get it rounded
    to 3 decimals (~100 m), enough to see the area but not the doorstep."""
    if item.latitude is None or item.longitude is None:
        return None
    if exact:
        return (item.latitude, item.longitude)
    return (round(item.latitude, 3), round(item.longitude, 3))


def _item_to_dict(item, show_contact):
    data = {
        "id": str(item.pk),
        "name": item.name,
        "category": item.category,
        "category_label": item.get_category_display(),
        "condition": item.condition,
        "condition_label": item.get_condition_display(),
        "photo_url": item.photo_url,
        "location_name": item.location_name,
        "transaction_type": item.transaction_type,
        "price": item.price,
        "status": item.status,
        "owner": item.owner.username,
        "created_at": item.created_at.isoformat(),
    }
    coords = _public_coords(item, show_contact)
    if coords is None:
        data["latitude"], data["longitude"] = None, None
    else:
        data["latitude"], data["longitude"] = coords
    # Only set when the radius filter is on.
    if hasattr(item, "distance_km"):
        data["distance_km"] = round(item.distance_km, 2)
    # Contact info is only for logged-in users.
    if show_contact:
        data["contact"] = item.contact
    return data


def items_json(request):
    _, items = filter_items(request.GET)
    page_obj = Paginator(items, PAGE_SIZE).get_page(request.GET.get("page"))
    show_contact = request.user.is_authenticated
    return JsonResponse(
        {
            "count": page_obj.paginator.count,
            "page": page_obj.number,
            "num_pages": page_obj.paginator.num_pages,
            "results": [_item_to_dict(item, show_contact) for item in page_obj],
        }
    )


def item_detail(request, pk):
    item = get_object_or_404(Item.objects.select_related("owner"), pk=pk)
    exact = request.user.is_authenticated
    context = _panel_context(request, item)
    context["show_contact"] = exact
    context["map_exact"] = exact
    coords = _public_coords(item, exact)
    if coords is not None:
        # Pre-formatted strings: the template must not localise the decimals.
        digits = 6 if exact else 3
        context["map_lat"] = f"{coords[0]:.{digits}f}"
        context["map_lng"] = f"{coords[1]:.{digits}f}"
    return render(request, "katalog/detail.html", context)


def item_detail_json(request, pk):
    item = get_object_or_404(Item.objects.select_related("owner"), pk=pk)
    data = _item_to_dict(item, request.user.is_authenticated)
    data["description"] = item.description
    return JsonResponse(data)


# --- Create / update / delete (HTMX modal + partials) -------------------------


def _form_response(request, form, item=None):
    # from_detail: the form was opened on the detail page, so after saving we
    # reload that page instead of swapping a catalog card.
    from_detail = request.POST.get("from_detail") or request.GET.get("from_detail")
    context = {"form": form, "item": item, "from_detail": from_detail}
    # A form that comes back with errors answers 422 (Unprocessable Entity).
    status = 422 if form.errors else 200
    response = render(request, "katalog/_item_form.html", context, status=status)
    if status == 422:
        # The form's hx-target is the grid (where a saved card goes); errors
        # belong back in the modal instead.
        response["HX-Retarget"] = "#modal-body"
        response["HX-Reswap"] = "innerHTML"
    return response


def _card_response(request, item):
    item.pending_count = item.requests.filter(status=PENDING).count()
    return render(request, "katalog/_item_card.html", {"item": item})


@login_required(login_url=LOGIN_URL)
@ratelimit(key="user", rate="10/m", method="POST", block=False)
def item_create(request):
    if request.limited:
        return toast_only(TOO_FAST, status=429)
    form = ItemForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.owner = request.user
        # OpenStreetMap: turn the place name into coordinates for the map.
        on_map = geocoding.geocode_item(item)
        item.save()
        if not is_htmx(request):
            return redirect("katalog:item_detail", pk=item.pk)
        if not on_map:
            return add_toast(_card_response(request, item), NOT_ON_MAP, "info")
        return add_toast(_card_response(request, item), "Barang berhasil dipasang.")

    return _form_response(request, form)


@login_required(login_url=LOGIN_URL)
def item_update(request, pk):
    item = get_object_or_404(Item, pk=pk)
    # Only the owner may edit (same check as Tutorial 04).
    if item.owner != request.user:
        raise PermissionDenied
    form = ItemForm(request.POST or None, instance=item)

    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        on_map = True
        # Only call the API when the place changed (or never resolved before).
        if "location_name" in form.changed_data or item.latitude is None:
            on_map = geocoding.geocode_item(item)
        item.save()
        if request.POST.get("from_detail"):
            return hx_redirect(reverse("katalog:item_detail", args=[item.pk]))
        # Swap the edited card in place instead of the form's default target.
        response = _card_response(request, item)
        response["HX-Retarget"] = f"#item-{item.pk}"
        response["HX-Reswap"] = "outerHTML"
        if not on_map:
            return add_toast(response, NOT_ON_MAP, "info")
        return add_toast(response, "Perubahan disimpan.")

    return _form_response(request, form, item)


@require_POST
@login_required(login_url=LOGIN_URL)
def item_soft_delete(request, pk):
    item = get_object_or_404(Item, pk=pk)
    if item.owner != request.user:
        raise PermissionDenied
    item.soft_delete()
    if request.POST.get("from_detail"):
        return hx_redirect(reverse("katalog:catalog"))
    # 204 = no swap: optimistic.js already hid the card, and keeping the hidden
    # element in the page gives the Undo button a place to put the card back.
    return toast_only(
        f"“{item.name}” dihapus.",
        "info",
        status=204,
        undo=reverse("katalog:item_restore", args=[item.pk]),
        target=f"#item-{item.pk}",
    )


@require_POST
@login_required(login_url=LOGIN_URL)
def item_restore(request, pk):
    # all_objects: the item is soft-deleted, so the default manager hides it.
    item = get_object_or_404(Item.all_objects, pk=pk)
    if item.owner != request.user:
        raise PermissionDenied
    item.restore()
    return add_toast(_card_response(request, item), "Barang dikembalikan.")


# --- Requests: the panel on the detail page -----------------------------------


def _panel_context(request, item):
    """What the "Ajukan" panel on the detail page needs: the viewer's own
    open request (if any) and which of the 3 steps to highlight."""
    my_request = None
    if request.user.is_authenticated and item.owner != request.user:
        my_request = item.requests.filter(
            requester=request.user, status__in=[PENDING, DITERIMA]
        ).first()
    if item.status == Item.Status.SELESAI:
        step = 3
    elif my_request and my_request.status == DITERIMA:
        step = 2
    else:
        step = 1
    return {"item": item, "my_request": my_request, "step": step}


def _panel_response(request, item):
    return render(request, "katalog/_request_panel.html", _panel_context(request, item))


@require_POST
@login_required(login_url=LOGIN_URL)
@ratelimit(key="user", rate="10/m", method="POST", block=False)
def request_create(request, pk):
    if request.limited:
        return toast_only(TOO_FAST, status=429)
    item = get_object_or_404(Item.objects.select_related("owner"), pk=pk)
    if item.owner == request.user:
        raise PermissionDenied
    if item.status != Item.Status.TERSEDIA:
        return toast_only("Barang ini sudah tidak tersedia.", status=409)
    if item.requests.filter(requester=request.user, status=PENDING).exists():
        return toast_only("Kamu sudah mengajukan barang ini. Tunggu balasan pemilik ya.", status=409)

    ItemRequest.objects.create(
        item=item,
        requester=request.user,
        message=strip_tags(request.POST.get("message", "")).strip(),
    )
    return add_toast(
        _panel_response(request, item), "Pengajuan terkirim. Tunggu balasan pemilik ya."
    )


# --- Requests: "Pusat permintaan" (incoming / outgoing) -----------------------

# ?status= tabs of the incoming list, as in design 07.
INCOMING_TABS = {
    "ditinjau": PENDING,
    "disetujui": DITERIMA,
    "selesai": ItemRequest.Status.SELESAI,
}


@login_required(login_url=LOGIN_URL)
def requests_page(request):
    # The template reads the item, its owner and the requester of every row,
    # so join them all up front (one query instead of one per row).
    requests = ItemRequest.objects.select_related("item", "item__owner", "requester", "review")

    if request.GET.get("tab") == "keluar":
        context = {"tab": "keluar", "rows": requests.filter(requester=request.user)}
        return render(request, "katalog/requests.html", context)

    incoming = requests.filter(item__owner=request.user)
    status_key = request.GET.get("status")
    if status_key not in INCOMING_TABS:
        status_key = "ditinjau"
    context = {
        "tab": "masuk",
        "status_key": status_key,
        "rows": incoming.filter(status=INCOMING_TABS[status_key]),
        "counts": {
            "ditinjau": incoming.filter(status=PENDING).count(),
            "disetujui": incoming.filter(status=DITERIMA).count(),
            "selesai": incoming.filter(status=ItemRequest.Status.SELESAI).count(),
        },
    }
    return render(request, "katalog/requests.html", context)


def _row_response(request, req, message):
    """The updated row of the request center, plus a toast."""
    response = render(request, "katalog/_request_row.html", {"req": req})
    return add_toast(response, message)


# Each action below finds the request with get_object_or_404 *and* the rule of
# who may do it (owner or requester) and in which status. Anything else -
# someone else's request, or a request that already moved on - is a 404.


@require_POST
@login_required(login_url=LOGIN_URL)
def request_accept(request, pk):
    req = get_object_or_404(ItemRequest, pk=pk, item__owner=request.user, status=PENDING)
    req.status = DITERIMA
    req.save()
    # One item goes to one person: the other waiting requests are rejected.
    req.item.requests.filter(status=PENDING).update(status=DITOLAK)
    req.item.status = Item.Status.DIPESAN
    req.item.save()

    # Several rows changed at once, so HTMX reloads the whole page; the toast
    # comes from Django messages after the reload.
    messages.success(request, "Permintaan diterima. Peminat lain otomatis ditolak.")
    response = HttpResponse()
    response["HX-Refresh"] = "true"
    return response


@require_POST
@login_required(login_url=LOGIN_URL)
def request_reject(request, pk):
    req = get_object_or_404(ItemRequest, pk=pk, item__owner=request.user, status=PENDING)
    req.status = DITOLAK
    req.save()
    return _row_response(request, req, "Permintaan ditolak.")


@require_POST
@login_required(login_url=LOGIN_URL)
def request_cancel(request, pk):
    req = get_object_or_404(
        ItemRequest, pk=pk, requester=request.user, status__in=[PENDING, DITERIMA]
    )
    if req.status == DITERIMA:
        # The item was booked for this requester; make it available again.
        req.item.status = Item.Status.TERSEDIA
        req.item.save()
    req.status = ItemRequest.Status.DIBATALKAN
    req.save()

    if request.POST.get("from_detail"):
        return add_toast(_panel_response(request, req.item), "Pengajuan dibatalkan.")
    return _row_response(request, req, "Pengajuan dibatalkan.")


@require_POST
@login_required(login_url=LOGIN_URL)
def request_complete(request, pk):
    """The handover happened. Padjri's review module keys off SELESAI."""
    req = get_object_or_404(ItemRequest, pk=pk, item__owner=request.user, status=DITERIMA)
    req.status = ItemRequest.Status.SELESAI
    req.save()
    req.item.status = Item.Status.SELESAI
    req.item.save()
    return _row_response(request, req, "Serah terima selesai. Terima kasih sudah berbagi!")


# --- "Barang saya" + bulk actions ---------------------------------------------


def _my_items_context(request, tab):
    tab = "terhapus" if tab == "terhapus" else "aktif"
    items = (
        Item.all_objects.filter(owner=request.user, is_deleted=tab == "terhapus")
        .annotate(pending_count=Count("requests", filter=Q(requests__status=PENDING)))
        .order_by("-created_at")
    )
    return {"tab": tab, "items": items}


@login_required(login_url=LOGIN_URL)
def my_items(request):
    context = _my_items_context(request, request.GET.get("tab"))
    return render(request, "katalog/my_items.html", context)


def _mark_done(item):
    """Bulk "Tandai selesai": finish the item and close its open requests."""
    item.status = Item.Status.SELESAI
    item.save()
    item.requests.filter(status=DITERIMA).update(status=ItemRequest.Status.SELESAI)
    item.requests.filter(status=PENDING).update(status=DITOLAK)


@require_POST
@login_required(login_url=LOGIN_URL)
@ratelimit(key="user", rate="10/m", method="POST", block=False)
def bulk_action(request):
    if request.limited:
        return toast_only(TOO_FAST, status=429)
    action = request.POST.get("action")
    ids = request.POST.getlist("ids")
    if not ids:
        return toast_only("Pilih minimal satu barang dulu.", status=400)

    # owner=request.user is the security check: ids of other people's items
    # simply match nothing. A tampered id that isn't a UUID raises ValidationError.
    try:
        mine = list(Item.all_objects.filter(owner=request.user, pk__in=ids))
    except ValidationError:
        return toast_only("Pilihan barang tidak valid.", status=400)

    if action == "delete":
        chosen = [item for item in mine if not item.is_deleted]
        for item in chosen:
            item.soft_delete()
        message = f"{len(chosen)} barang dihapus. Kembalikan lewat tab Terhapus."
    elif action == "done":
        chosen = [item for item in mine if not item.is_deleted and item.status != Item.Status.SELESAI]
        for item in chosen:
            _mark_done(item)
        message = f"{len(chosen)} barang ditandai selesai."
    elif action == "restore":
        chosen = [item for item in mine if item.is_deleted]
        for item in chosen:
            item.restore()
        message = f"{len(chosen)} barang dikembalikan."
    else:
        return toast_only("Aksi tidak dikenal.", status=400)

    context = _my_items_context(request, request.POST.get("tab"))
    response = render(request, "katalog/_my_items_table.html", context)
    return add_toast(response, message)
