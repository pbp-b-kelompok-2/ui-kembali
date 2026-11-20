"""Django REST Framework endpoints for the Review & Report module.

Business rules live in review_report.services and are shared with the website
views, so the web app and the Flutter app can never disagree.
"""
from functools import wraps

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
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

from katalog.models import Item, ItemRequest

from . import services
from .forms import ReviewFilterForm
from .models import Report, Review
from .serializers import (
    ReportCreateSerializer, ReportSerializer, ReportUpdateSerializer,
    ReviewInputSerializer, ReviewSerializer, ReviewTransactionSerializer,
)

PAGE_SIZE = 10
AUTH = [SessionAuthentication]


class RRPagination(PageNumberPagination):
    """Same envelope as katalog's API: count / page / num_pages / results."""

    page_size = PAGE_SIZE

    def get_paginated_response(self, data):
        return Response({
            "count": self.page.paginator.count,
            "page": self.page.number,
            "num_pages": self.page.paginator.num_pages,
            "results": data,
        })


def _paginated(request, rows, serializer_class, **extra):
    paginator = RRPagination()
    page = paginator.paginate_queryset(rows, request)
    serializer = serializer_class(page, many=True, context={"request": request})
    response = paginator.get_paginated_response(serializer.data)
    response.data.update(extra)
    return response


def service_errors(view):
    """Map the services' Django exceptions to the JSON the website's pages imply.

    PermissionDenied -> 403, ValidationError (rule not satisfied) -> 409.
    """
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except DjangoPermissionDenied as exc:
            raise PermissionDenied(str(exc))
        except DjangoValidationError as exc:
            return Response({"detail": " ".join(exc.messages)}, status=status.HTTP_409_CONFLICT)
    return wrapped


def _reviews():
    return Review.objects.select_related(
        "item_request__item__owner", "item_request__requester",
    )


def _filter_reviews(request, rows):
    """Same filters as the website: ?rating=1..5 and ?transaction_type=ADOPSI|JUAL."""
    form = ReviewFilterForm(request.query_params)
    if form.is_valid():
        if form.cleaned_data["rating"]:
            rows = rows.filter(rating=form.cleaned_data["rating"])
        if form.cleaned_data["transaction_type"]:
            rows = rows.filter(
                item_request__item__transaction_type=form.cleaned_data["transaction_type"],
            )
    return rows


def _visible_report(request, pk):
    """Reporter sees own reports; an authorised moderator sees any."""
    rows = Report.objects.select_related("target_item", "target_user", "reporter")
    if not services.can_moderate(request.user):
        rows = rows.filter(reporter=request.user)
    return get_object_or_404(rows, pk=pk)


def _own_report(request, pk):
    return get_object_or_404(
        Report.objects.select_related("target_item", "target_user"),
        pk=pk, reporter=request.user,
    )


# --- meta ---------------------------------------------------------------------

@api_view(["GET"])
@authentication_classes(AUTH)
@permission_classes([])
def meta(request):
    """Choices for dropdowns in the app (report category/status, ratings)."""
    return Response({
        "report_categories": [{"value": v, "label": l} for v, l in Report.Category.choices],
        "report_statuses": [{"value": v, "label": l} for v, l in Report.Status.choices],
        "transaction_types": [{"value": v, "label": l} for v, l in Item.TransactionType.choices],
        "ratings": [1, 2, 3, 4, 5],
    })


# --- transactions & reviews ---------------------------------------------------

@api_view(["GET"])
@authentication_classes(AUTH)
@permission_classes([IsAuthenticated])
def transaction_list(request):
    """Riwayat Transaksi with review_id / can_review for each row."""
    rows = (
        ItemRequest.objects
        .filter(Q(requester=request.user) | Q(item__owner=request.user))
        .select_related("item", "item__owner", "requester", "review")
        .order_by("-updated_at")
    )
    return _paginated(request, rows, ReviewTransactionSerializer)


@api_view(["GET"])
@authentication_classes(AUTH)
@permission_classes([IsAuthenticated])
def my_review_list(request):
    """Ulasan Saya: reviews I wrote."""
    rows = _filter_reviews(request, _reviews().filter(item_request__requester=request.user))
    return _paginated(request, rows, ReviewSerializer)


@api_view(["GET"])
@authentication_classes(AUTH)
@permission_classes([])
def owner_review_list(request, pk):
    """Public: reviews received by a seller, plus rating summary."""
    owner = get_object_or_404(get_user_model(), pk=pk)
    rows = _filter_reviews(request, _reviews().filter(item_request__item__owner=owner))
    summary = services.rating_summary(owner)
    average = summary["average"]
    return _paginated(
        request, rows, ReviewSerializer,
        owner={"id": owner.pk, "username": owner.username},
        summary={
            "average": round(average, 2) if average is not None else None,
            "count": summary["count"],
        },
    )


@api_view(["POST"])
@authentication_classes(AUTH)
@permission_classes([IsAuthenticated])
@service_errors
def review_create(request, pk):
    """Ulas transaksi yang SELESAI. Only that transaction's requester may."""
    deal = get_object_or_404(
        ItemRequest.objects.select_related("item__owner", "requester"), pk=pk,
    )
    services.review_eligibility(deal, request.user)
    if Review.objects.filter(item_request=deal).exists():
        return Response(
            {"detail": "Transaksi ini sudah diulas. Edit ulasan yang ada."},
            status=status.HTTP_409_CONFLICT,
        )
    payload = ReviewInputSerializer(data=request.data)
    payload.is_valid(raise_exception=True)
    review = services.create_review(deal, request.user, **payload.validated_data)
    review = _reviews().get(pk=review.pk)
    return Response(
        ReviewSerializer(review, context={"request": request}).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "HEAD", "PUT", "PATCH", "DELETE"])
@authentication_classes(AUTH)
@permission_classes([])
@service_errors
def review_detail(request, pk):
    review = get_object_or_404(_reviews(), pk=pk)
    context = {"request": request}
    if request.method in ("GET", "HEAD"):  # public, like the website
        return Response(ReviewSerializer(review, context=context).data)

    if not request.user.is_authenticated:
        raise PermissionDenied("Silakan masuk terlebih dahulu.")
    if request.method == "DELETE":
        services.delete_review(review, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    services._review_author(review, request.user)
    partial = request.method == "PATCH"
    payload = ReviewInputSerializer(data=request.data, partial=partial)
    payload.is_valid(raise_exception=True)
    values = {"rating": review.rating, "comment": review.comment, **payload.validated_data}
    review = services.update_review(review, request.user, **values)
    return Response(ReviewSerializer(_reviews().get(pk=review.pk), context=context).data)


# --- reports ------------------------------------------------------------------

@api_view(["GET", "POST"])
@authentication_classes(AUTH)
@permission_classes([IsAuthenticated])
@service_errors
def report_list(request):
    """GET: Laporan Saya (?status=, ?category=). POST: create a private report."""
    if request.method == "POST":
        payload = ReportCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        report = services.create_report(request.user, **payload.validated_data)
        report = _own_report(request, report.pk)
        return Response(
            ReportSerializer(report, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    rows = Report.objects.filter(reporter=request.user).select_related("target_item", "target_user")
    category = request.query_params.get("category", "")
    state = request.query_params.get("status", "")
    if category in Report.Category.values:
        rows = rows.filter(category=category)
    if state in Report.Status.values:
        rows = rows.filter(status=state)
    return _paginated(request, rows, ReportSerializer)


@api_view(["GET", "HEAD", "PUT", "PATCH", "DELETE"])
@authentication_classes(AUTH)
@permission_classes([IsAuthenticated])
@service_errors
def report_detail(request, pk):
    context = {"request": request}
    if request.method in ("GET", "HEAD"):
        return Response(ReportSerializer(_visible_report(request, pk), context=context).data)

    report = _own_report(request, pk)  # only the reporter edits/deletes
    if request.method == "DELETE":
        services.delete_report(report, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    services._pending_reporter(report, request.user)
    partial = request.method == "PATCH"
    payload = ReportUpdateSerializer(data=request.data, partial=partial)
    payload.is_valid(raise_exception=True)
    values = {"category": report.category, "description": report.description, **payload.validated_data}
    report = services.update_report(report, request.user, **values)
    return Response(ReportSerializer(_own_report(request, report.pk), context=context).data)
