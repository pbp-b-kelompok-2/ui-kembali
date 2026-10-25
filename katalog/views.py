import json

from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from .decorators import is_htmx, login_required_htmx, owner_required, toast_response
from .filters import filter_items
from .forms import ItemForm
from .models import Item

PAGE_SIZE = 12


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
    if show_contact:
        data["contact"] = item.contact
    return data


def items_json(request):
    _, qs = filter_items(request.GET)
    page_obj = Paginator(qs.defer(None), PAGE_SIZE).get_page(request.GET.get("page"))
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
    return render(
        request,
        "katalog/detail.html",
        {"item": item, "show_contact": request.user.is_authenticated},
    )


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
    item.save()
    if not is_htmx(request):
        return redirect("katalog:item_detail", pk=item.pk)
    return _with_toast(_card_response(request, item), "Barang berhasil dipasang.")


@owner_required()
def item_update(request, item):
    if request.method != "POST":
        return _form_response(request, ItemForm(instance=item), item)
    form = ItemForm(request.POST, instance=item)
    if not form.is_valid():
        return _form_response(request, form, item, status=422)
    item = form.save()
    if request.POST.get("from_detail"):
        response = HttpResponse(status=204)
        response["HX-Redirect"] = reverse("katalog:item_detail", args=[item.pk])
        return response
    response = _card_response(request, item)
    response["HX-Retarget"] = f"#item-{item.pk}"
    response["HX-Reswap"] = "outerHTML"
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
