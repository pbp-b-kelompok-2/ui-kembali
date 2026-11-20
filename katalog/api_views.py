from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import (
    api_view, authentication_classes, permission_classes,
)
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import geocoding
from .filters import filter_items
from .models import Item, ItemRequest
from .permissions import IsOwnerOrReadOnly
from .serializers import ItemRequestSerializer, ItemSerializer, TransactionSerializer

PAGE_SIZE = 12


class ItemPagination(PageNumberPagination):
    """Same envelope as the website's /katalog/json/ so clients see one shape."""

    page_size = PAGE_SIZE

    def get_paginated_response(self, data):
        return Response({
            "count": self.page.paginator.count,
            "page": self.page.number,
            "num_pages": self.page.paginator.num_pages,
            "results": data,
        })


def _paginated(request, rows, serializer_class):
    paginator = ItemPagination()
    page = paginator.paginate_queryset(rows, request)
    serializer = serializer_class(page, many=True, context={"request": request})
    return paginator.get_paginated_response(serializer.data)


def _paginated_items(request, items):
    return _paginated(request, items, ItemSerializer)


@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def transaction_list(request):
    """Riwayat transaksi: requests I made or received. ?type=ADOPSI|JUAL filters."""
    rows = (
        ItemRequest.objects
        .filter(Q(requester=request.user) | Q(item__owner=request.user))
        .select_related("item", "item__owner", "requester")
        .order_by("-updated_at")
    )
    kind = request.query_params.get("type", "")
    if kind in Item.TransactionType.values:
        rows = rows.filter(item__transaction_type=kind)
    return _paginated(request, rows, TransactionSerializer)


@api_view(["GET", "HEAD", "POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsOwnerOrReadOnly])
def item_list(request):
    if request.method in ("GET", "HEAD"):
        # Same query string as the catalog page: q, category, condition, type,
        # location, min_price, max_price, sort, near, lat, lng, radius, page.
        _, items = filter_items(request.query_params)
        return _paginated_items(request, items)

    serializer = ItemSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    # OpenStreetMap: turn the place name into coordinates for the map.
    coords = geocoding.geocode(serializer.validated_data["location_name"])
    latitude, longitude = coords or (None, None)
    serializer.save(owner=request.user, latitude=latitude, longitude=longitude)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def my_item_list(request):
    items = (
        Item.objects.filter(owner=request.user)
        .select_related("owner")
        .order_by("-created_at")
    )
    return _paginated_items(request, items)


@api_view(["GET", "HEAD", "PUT", "PATCH", "DELETE"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsOwnerOrReadOnly])
def item_detail(request, item_id):
    item = get_object_or_404(Item.objects.select_related("owner"), pk=item_id)
    # has_permission already ran; function views must call the object check by hand.
    permission = IsOwnerOrReadOnly()
    if not permission.has_object_permission(request, None, item):
        raise PermissionDenied(permission.message)

    context = {"request": request}
    if request.method in ("GET", "HEAD"):
        return Response(ItemSerializer(item, context=context).data)

    if request.method == "DELETE":
        item.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = ItemSerializer(
        item, data=request.data, partial=request.method == "PATCH", context=context,
    )
    serializer.is_valid(raise_exception=True)
    extra = {}
    place = serializer.validated_data.get("location_name")
    # Only call the geocoder when the place changed (or never resolved before).
    if (place is not None and place != item.location_name) or item.latitude is None:
        coords = geocoding.geocode(place or item.location_name)
        extra["latitude"], extra["longitude"] = coords or (None, None)
    serializer.save(**extra)
    return Response(serializer.data)


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def item_request_create(request, item_id):
    """Ask the owner for an item ("Ajukan"). Mirrors katalog.views.request_create."""
    item = get_object_or_404(Item.objects.select_related("owner"), pk=item_id)
    if item.owner_id == request.user.pk:
        return Response(
            {"detail": "You cannot request your own item."},
            status=status.HTTP_403_FORBIDDEN,
        )
    if item.status != Item.Status.TERSEDIA:
        return Response(
            {"detail": "Barang ini sudah tidak tersedia."},
            status=status.HTTP_409_CONFLICT,
        )
    if item.requests.filter(
        requester=request.user, status=ItemRequest.Status.PENDING,
    ).exists():
        return Response(
            {"detail": "Kamu sudah mengajukan barang ini. Tunggu balasan pemilik ya."},
            status=status.HTTP_409_CONFLICT,
        )
    serializer = ItemRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save(item=item, requester=request.user)
    return Response(serializer.data, status=status.HTTP_201_CREATED)
