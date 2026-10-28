import json
from functools import wraps
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.cache import patch_vary_headers
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from katalog.decorators import is_htmx, login_required_htmx
from katalog.models import Item, ItemRequest
from .forms import ReviewForm, ReportForm, ReviewFilterForm
from .models import Review, Report
from . import services


def module_view(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        try:
            response = view(request, *args, **kwargs)
        except PermissionDenied as exc:
            response = page(request, {'kind': 'error', 'title': 'Akses ditolak', 'error': str(exc)}, 403)
        except ValidationError as exc:
            response = page(request, {'kind': 'error', 'title': 'Aksi belum dapat dilakukan', 'error': ' '.join(exc.messages)}, 409)
        patch_vary_headers(response, ['HX-Request', 'Cookie'])
        return response
    return never_cache(wrapped)


def page(request, context, status=200):
    partial = is_htmx(request) and request.headers.get('HX-History-Restore-Request') != 'true'
    response = render(request, 'review_report/_content.html' if partial else 'review_report/page.html', context, status=status)
    if status >= 400:
        response['HX-Trigger'] = json.dumps({'toast': {'msg': 'Periksa pesan pada halaman.', 'level': 'error'}})
    return response


def success(request, url, msg):
    if not is_htmx(request):
        messages.success(request, msg)
        return redirect(url)
    # Render the destination through its view so the submitted form is replaced.
    from django.urls import resolve
    match = resolve(url)
    original_get, original_method, original_path, original_path_info = request.GET, request.method, request.path, request.path_info
    request.GET, request.method = request.GET.copy(), 'GET'
    request.path = request.path_info = url
    request.GET.clear()
    try:
        response = match.func(request, **match.kwargs)
    finally:
        request.GET, request.method = original_get, original_method
        request.path, request.path_info = original_path, original_path_info
    response['HX-Push-Url'] = url
    response['HX-Trigger'] = json.dumps({'toast': {'msg': msg, 'level': 'success'}})
    return response


def reviews():
    return Review.objects.select_related('item_request__item__owner', 'item_request__requester')


def paginate(request, qs):
    params = request.GET.copy()
    params.pop('page', None)
    return {'page_obj': Paginator(qs, 10).get_page(request.GET.get('page')), 'querystring': params.urlencode()}


def review_list(request, owner=None):
    qs = reviews()
    title = 'Ulasan Saya'
    summary = None
    if owner:
        qs = qs.filter(item_request__item__owner=owner)
        title = f'Ulasan untuk {owner.username}'
        summary = services.rating_summary(owner)
    else:
        qs = qs.filter(item_request__requester=request.user)
    form = ReviewFilterForm(request.GET)
    if form.is_valid():
        if form.cleaned_data['rating']:
            qs = qs.filter(rating=form.cleaned_data['rating'])
        if form.cleaned_data['transaction_type']:
            qs = qs.filter(item_request__item__transaction_type=form.cleaned_data['transaction_type'])
    return page(request, dict(kind='reviews', title=title, filter_form=form, summary=summary, **paginate(request, qs)))


@module_view
@login_required_htmx
@require_GET
def my_reviews(request):
    return review_list(request)


@module_view
@require_GET
def owner_reviews(request, pk):
    return review_list(request, get_object_or_404(get_user_model(), pk=pk))


@module_view
@require_GET
def review_detail(request, pk):
    review = get_object_or_404(reviews(), pk=pk)
    return page(request, {'kind': 'review_detail', 'title': 'Ulasan transaksi', 'review': review, 'deal': review.item_request})


@module_view
@login_required_htmx
@require_http_methods(['GET', 'POST'])
def review_create(request, pk):
    deal = get_object_or_404(ItemRequest.objects.select_related('item__owner', 'requester'), pk=pk)
    services.review_eligibility(deal, request.user)
    existing = Review.objects.filter(item_request=deal).first()
    if existing:
        if request.method == 'POST':
            raise ValidationError('Transaksi ini sudah diulas. Buka Ulasan Saya untuk mengeditnya.')
        return redirect('review_report:review_detail', pk=existing.pk)
    form = ReviewForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        try:
            review = services.create_review(deal, request.user, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, ' '.join(exc.messages))
        else:
            return success(request, reverse('review_report:review_detail', args=[review.pk]), 'Ulasan berhasil dikirim.')
    return page(request, {'kind': 'review_form', 'title': 'Transaksi selesai!', 'form': form, 'deal': deal}, 422 if form.is_bound else 200)


@module_view
@login_required_htmx
@require_http_methods(['GET', 'POST'])
def review_update(request, pk):
    review = get_object_or_404(reviews(), pk=pk)
    services._review_author(review, request.user)
    form = ReviewForm(request.POST if request.method == 'POST' else None, initial={'rating': review.rating, 'comment': review.comment})
    if request.method == 'POST' and form.is_valid():
        try:
            review = services.update_review(review, request.user, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, ' '.join(exc.messages))
        else:
            return success(request, reverse('review_report:review_detail', args=[review.pk]), 'Perubahan ulasan disimpan.')
    return page(request, {'kind': 'review_form', 'title': 'Edit ulasan', 'form': form, 'deal': review.item_request, 'review': review}, 422 if form.is_bound else 200)


@module_view
@login_required_htmx
@require_POST
def review_delete(request, pk):
    services.delete_review(get_object_or_404(reviews(), pk=pk), request.user)
    return success(request, reverse('review_report:my_reviews'), 'Ulasan dihapus.')


def owned_report(request, pk, staff=False):
    qs = Report.objects.select_related('target_item', 'target_user', 'reporter')
    if not (staff and services.can_moderate(request.user)):
        qs = qs.filter(reporter=request.user)
    return get_object_or_404(qs, pk=pk)


@module_view
@login_required_htmx
@require_GET
def my_reports(request):
    qs = Report.objects.filter(reporter=request.user).select_related('target_item', 'target_user')
    status = request.GET.get('status', '')
    if status in Report.Status.values:
        qs = qs.filter(status=status)
    return page(request, dict(kind='reports', title='Laporan Saya', statuses=Report.Status.choices, selected_status=status, **paginate(request, qs)))


@module_view
@login_required_htmx
@require_GET
def report_detail(request, pk):
    report = owned_report(request, pk, staff=True)
    return page(request, {'kind': 'report_detail', 'title': 'Detail laporan privat', 'report': report})


def report_form(request, *, target_item=None, target_user=None, report=None):
    if report:
        services._pending_reporter(report, request.user)
    form = ReportForm(request.POST if request.method == 'POST' else None,
                      initial={'category': report.category, 'description': report.description} if report else None)
    if request.method == 'POST' and form.is_valid():
        try:
            if report:
                saved = services.update_report(report, request.user, **form.cleaned_data)
            else:
                saved = services.create_report(request.user, target_item=target_item, target_user=target_user, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, ' '.join(exc.messages))
        else:
            return success(request, reverse('review_report:report_detail', args=[saved.pk]), 'Laporan berhasil disimpan.')
    return page(request, {'kind': 'report_form', 'title': 'Edit laporan' if report else 'Buat laporan privat', 'form': form,
                          'target_item': target_item or (report.target_item if report else None), 'target_user': target_user or (report.target_user if report else None)}, 422 if form.is_bound else 200)


@module_view
@login_required_htmx
@require_http_methods(['GET', 'POST'])
def report_item(request, pk):
    item = get_object_or_404(Item, pk=pk)
    if item.owner_id == request.user.pk:
        raise PermissionDenied('Tidak dapat melaporkan barang sendiri.')
    return report_form(request, target_item=item)


@module_view
@login_required_htmx
@require_http_methods(['GET', 'POST'])
def report_user(request, pk):
    user = get_object_or_404(get_user_model(), pk=pk)
    if user.pk == request.user.pk:
        raise PermissionDenied('Tidak dapat melaporkan diri sendiri.')
    return report_form(request, target_user=user)


@module_view
@login_required_htmx
@require_http_methods(['GET', 'POST'])
def report_update(request, pk):
    return report_form(request, report=owned_report(request, pk))


@module_view
@login_required_htmx
@require_POST
def report_delete(request, pk):
    services.delete_report(owned_report(request, pk), request.user)
    return success(request, reverse('review_report:my_reports'), 'Laporan dihapus.')


@module_view
@login_required_htmx
@require_GET
def transactions(request):
    qs = ItemRequest.objects.filter(Q(requester=request.user) | Q(item__owner=request.user)).select_related('item__owner', 'requester', 'review')
    return page(request, dict(kind='transactions', title='Riwayat Transaksi', **paginate(request, qs)))
