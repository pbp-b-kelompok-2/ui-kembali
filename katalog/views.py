import json
import uuid

from django.core.paginator import Paginator
from django.db.models import Count, Q, QuerySet
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from .decorators import is_htmx, login_required_htmx, owner_required, toast_response
from . import geocoding, services
from .filters import RADIUS_CHOICES, filter_items
from .forms import ItemForm
from .models import Item, ItemRequest
from .services import RequestError

PAGE_SIZE = 12
NOT_ON_MAP = "Tersimpan, tapi lokasinya belum ketemu di peta. Coba nama tempat yang lebih umum."


def _list_context(request):
    form, qs = filter_items(request.GET)
    # get_page() turns a bad or too-large ?page= into the first/last page.
    page_obj = Paginator(qs, PAGE_SIZE).get_page(request.GET.get("page"))
    # Page links keep every filter but replace ?page=.
    params = request.GET.copy()
    params.pop("page", None)
    return {
        "form": form,
        "page_obj": page_obj,
        "chips": form.active_chips(),
        "querystring": params.urlencode(),
        "radius_choices": RADIUS_CHOICES,
    }


def catalog_page(request):
    context = _list_context(request)
    # HTMX history restore (after hx-push-url) asks this URL for the grid only.
    if request.headers.get("HX-Request") and not request.headers.get(
        "HX-History-Restore-Request"
    ):
        return render(request, "katalog/_item_grid.html", context)
    return render(request, "katalog/catalog.html", context)


def item_list_partial(request):
    return render(request, "katalog/_item_grid.html", _list_context(request))


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
    data["latitude"], data["longitude"] = _public_coords(item, show_contact) or (None, None)
    if hasattr(item, "distance_km"):
        data["distance_km"] = round(item.distance_km, 2)
    if show_contact:
        data["contact"] = item.contact
    return data


def items_json(request):
    _, qs = filter_items(request.GET)
    if isinstance(qs, QuerySet):
        qs = qs.defer(None)
    page_obj = Paginator(qs, PAGE_SIZE).get_page(request.GET.get("page"))
    show_contact = request.user.is_authenticated
    return JsonResponse(
        {
            "count": page_obj.paginator.count,
            "page": page_obj.number,
            "num_pages": page_obj.paginator.num_pages,
            "results": [_item_to_dict(i, show_contact) for i in page_obj],
        }
    )


def item_detail(request, pk):
    item = get_object_or_404(Item.objects.select_related("owner"), pk=pk)
    exact = request.user.is_authenticated
    context = {"item": item, "show_contact": exact, "map_exact": exact}
    if coords := _public_coords(item, exact):
        # Pre-formatted strings: the template must not localise the decimals.
        digits = 6 if exact else 3
        context["map_lat"], context["map_lng"] = (f"{c:.{digits}f}" for c in coords)
    context.update(_panel_context(request, item))
    return render(request, "katalog/detail.html", context)


def item_detail_json(request, pk):
    item = get_object_or_404(Item.objects.select_related("owner"), pk=pk)
    data = _item_to_dict(item, request.user.is_authenticated)
    data["description"] = item.description
    return JsonResponse(data)


# --- Create / update / delete (HTMX modal + partials) -----------------------


def _with_toast(response, msg, level="success"):
    response["HX-Trigger"] = json.dumps({"toast": {"msg": msg, "level": level}})
    return response


def _form_response(request, form, item=None, status=200):
    # from_detail: the form was opened on the detail page, so after saving we
    # reload that page instead of swapping a catalog card.
    from_detail = request.POST.get("from_detail") or request.GET.get("from_detail")
    context = {"form": form, "item": item, "from_detail": from_detail}
    response = render(request, "katalog/_item_form.html", context, status=status)
    if status == 422:
        # The form's hx-target is the grid (where a saved card goes); errors
        # belong back in the modal instead.
        response["HX-Retarget"] = "#modal-body"
        response["HX-Reswap"] = "innerHTML"
    return response


def _card_response(request, item):
    item.pending_count = item.requests.filter(status="PENDING").count()
    return render(request, "katalog/_item_card.html", {"item": item})


@login_required_htmx
@ratelimit(key="user", rate="10/m", method="POST", block=False)
def item_create(request):
    if request.method != "POST":
        return _form_response(request, ItemForm())
    if getattr(request, "limited", False):
        return toast_response(
            "Terlalu banyak barang dalam semenit. Coba lagi sebentar.", "error", 429
        )
    form = ItemForm(request.POST)
    if not form.is_valid():
        return _form_response(request, form, status=422)
    item = form.save(commit=False)
    item.owner = request.user
    on_map = geocoding.geocode_item(item)
    item.save()
    if not is_htmx(request):
        return redirect("katalog:item_detail", pk=item.pk)
    if on_map:
        return _with_toast(_card_response(request, item), "Barang berhasil dipasang.")
    return _with_toast(_card_response(request, item), NOT_ON_MAP, "info")


@owner_required()
def item_update(request, item):
    if request.method != "POST":
        return _form_response(request, ItemForm(instance=item), item)
    form = ItemForm(request.POST, instance=item)
    if not form.is_valid():
        return _form_response(request, form, item, status=422)
    item = form.save(commit=False)
    on_map = True
    # Only call the API when the place changed (or never resolved before).
    if "location_name" in form.changed_data or item.latitude is None:
        on_map = geocoding.geocode_item(item)
    item.save()
    if request.POST.get("from_detail"):
        response = HttpResponse(status=204)
        response["HX-Redirect"] = reverse("katalog:item_detail", args=[item.pk])
        return response
    response = _card_response(request, item)
    response["HX-Retarget"] = f"#item-{item.pk}"
    response["HX-Reswap"] = "outerHTML"
    if not on_map:
        return _with_toast(response, NOT_ON_MAP, "info")
    return _with_toast(response, "Perubahan disimpan.")


@require_POST
@owner_required()
def item_soft_delete(request, item):
    item.soft_delete()
    if request.POST.get("from_detail"):
        response = HttpResponse(status=204)
        response["HX-Redirect"] = reverse("katalog:catalog")
        return response
    # 204 = no swap: optimistic.js already hid the card, and keeping the hidden
    # element in the page gives the Undo button a place to put the card back.
    return toast_response(
        f"“{item.name}” dihapus.",
        "info",
        status=204,
        undo=reverse("katalog:item_restore", args=[item.pk]),
        target=f"#item-{item.pk}",
    )


@require_POST
@owner_required(include_deleted=True)
def item_restore(request, item):
    item.restore()
    return _with_toast(_card_response(request, item), "Barang dikembalikan.")


# --- Requests: the panel on the detail page --------------------------------


def _panel_context(request, item):
    """What the "Ajukan" panel on the detail page needs: the viewer's own
    open request (if any) and which of the 3 steps to highlight."""
    my_request = None
    if request.user.is_authenticated and item.owner_id != request.user.id:
        my_request = item.requests.filter(
            requester=request.user,
            status__in=[ItemRequest.Status.PENDING, ItemRequest.Status.DITERIMA],
        ).first()
    if item.status == Item.Status.SELESAI:
        step = 3
    elif my_request and my_request.status == ItemRequest.Status.DITERIMA:
        step = 2
    else:
        step = 1
    return {"item": item, "my_request": my_request, "step": step}


def _panel_response(request, item):
    return render(request, "katalog/_request_panel.html", _panel_context(request, item))


@require_POST
@login_required_htmx
@ratelimit(key="user", rate="10/m", method="POST", block=False)
def request_create(request, pk):
    item = get_object_or_404(Item.objects.select_related("owner"), pk=pk)
    if getattr(request, "limited", False):
        return toast_response(
            "Terlalu banyak pengajuan dalam semenit. Coba lagi sebentar.", "error", 429
        )
    try:
        services.create_request(item, request.user, request.POST.get("message", ""))
    except RequestError as error:
        return toast_response(error.message, "error", error.status)
    return _with_toast(
        _panel_response(request, item), "Pengajuan terkirim. Tunggu balasan pemilik ya."
    )


# --- Requests: "Pusat permintaan" (incoming / outgoing) -----------------------

# ?status= tabs of the incoming list, as in design 07.
INCOMING_TABS = {
    "ditinjau": ItemRequest.Status.PENDING,
    "disetujui": ItemRequest.Status.DITERIMA,
    "selesai": ItemRequest.Status.SELESAI,
}


@login_required_htmx
def requests_page(request):
    # One query for the rows: the template reads the item, its owner and the
    # requester of every row, so join them all up front.
    base = ItemRequest.objects.select_related("item", "item__owner", "requester")
    context = {"tab": "keluar" if request.GET.get("tab") == "keluar" else "masuk"}
    if context["tab"] == "masuk":
        incoming = base.filter(item__owner=request.user)
        context["counts"] = incoming.aggregate(
            **{
                key: Count("pk", filter=Q(status=status))
                for key, status in INCOMING_TABS.items()
            }
        )
        status_key = request.GET.get("status")
        if status_key not in INCOMING_TABS:
            status_key = "ditinjau"
        context["status_key"] = status_key
        context["rows"] = incoming.filter(status=INCOMING_TABS[status_key])
    else:
        context["rows"] = base.filter(requester=request.user)
    return render(request, "katalog/requests.html", context)


REQUEST_ACTIONS = {
    "accept": (services.accept_request, "Permintaan diterima. Peminat lain otomatis ditolak."),
    "reject": (services.reject_request, "Permintaan ditolak."),
    "cancel": (services.cancel_request, "Pengajuan dibatalkan."),
    "complete": (services.complete_request, "Serah terima selesai. Terima kasih sudah berbagi!"),
}


@require_POST
@login_required_htmx
def request_action(request, pk, action):
    if action not in REQUEST_ACTIONS:
        raise Http404
    handler, message = REQUEST_ACTIONS[action]
    # Only the item's owner and the requester may even see the request;
    # anyone else gets the same 404 as for a request that doesn't exist.
    req = get_object_or_404(
        ItemRequest.objects.select_related("item", "item__owner", "requester").filter(
            Q(item__owner=request.user) | Q(requester=request.user)
        ),
        pk=pk,
    )
    try:
        rejected = handler(req, request.user)
    except RequestError as error:
        return toast_response(error.message, "error", error.status)
    if request.POST.get("from_detail"):
        return _with_toast(_panel_response(request, req.item), message)
    # Accepting rejects the item's other requests; their rows ride along as
    # out-of-band swaps so the whole list is right without a reload.
    response = render(
        request, "katalog/_request_row.html", {"req": req, "oob_rows": rejected or []}
    )
    return _with_toast(response, message)


# --- "Barang saya" + bulk actions ---------------------------------------------


def _my_items_context(request, tab):
    tab = "terhapus" if tab == "terhapus" else "aktif"
    items = (
        Item.all_objects.filter(owner=request.user, is_deleted=tab == "terhapus")
        .annotate(
            pending_count=Count(
                "requests", filter=Q(requests__status=ItemRequest.Status.PENDING)
            )
        )
        .order_by("-created_at")
    )
    return {"tab": tab, "items": items}


@login_required_htmx
def my_items(request):
    return render(
        request, "katalog/my_items.html", _my_items_context(request, request.GET.get("tab"))
    )


BULK_ACTIONS = {"delete", "done", "restore"}


@require_POST
@login_required_htmx
@ratelimit(key="user", rate="10/m", method="POST", block=False)
def bulk_action(request):
    if getattr(request, "limited", False):
        return toast_response("Terlalu banyak aksi dalam semenit. Coba lagi sebentar.", "error", 429)
    action = request.POST.get("action")
    if action not in BULK_ACTIONS:
        return toast_response("Aksi tidak dikenal.", "error", 400)
    ids = []
    for raw in request.POST.getlist("ids"):
        try:
            ids.append(uuid.UUID(raw))
        except ValueError:
            continue  # a tampered checkbox value; just skip it
    if not ids:
        return toast_response("Pilih minimal satu barang dulu.", "error", 400)

    # owner=request.user is the security check: ids of other people's items
    # simply match nothing.
    mine = Item.all_objects.filter(owner=request.user, pk__in=ids)
    now = timezone.now()
    if action == "delete":
        count = mine.filter(is_deleted=False).update(
            is_deleted=True, deleted_at=now, updated_at=now
        )
        message = f"{count} barang dihapus. Kembalikan lewat tab Terhapus."
    elif action == "done":
        count = services.mark_items_done(mine.filter(is_deleted=False))
        message = f"{count} barang ditandai selesai."
    else:
        count = mine.filter(is_deleted=True).update(
            is_deleted=False, deleted_at=None, updated_at=now
        )
        message = f"{count} barang dikembalikan."
    response = render(
        request,
        "katalog/_my_items_table.html",
        _my_items_context(request, request.POST.get("tab")),
    )
    return _with_toast(response, message)
