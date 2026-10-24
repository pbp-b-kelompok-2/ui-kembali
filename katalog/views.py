from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from .filters import filter_items
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
