"""Business rules shared by HTTP views and admin. Mutations reload locked rows."""
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count
from django.utils import timezone
from katalog.models import Item, ItemRequest
from .models import Review, Report


def require_user(user):
    if not user.is_authenticated:
        raise PermissionDenied('Silakan masuk terlebih dahulu.')


def review_eligibility(deal, user):
    require_user(user)
    if deal.requester_id != user.pk or deal.item.owner_id == user.pk:
        raise PermissionDenied('Hanya pengaju transaksi ini yang dapat memberi ulasan.')
    if deal.status != ItemRequest.Status.SELESAI:
        raise ValidationError('Permintaan transaksi belum selesai.')


def create_review(deal, user, *, rating, comment):
    try:
        with transaction.atomic():
            deal = ItemRequest.objects.select_for_update().select_related('item').get(pk=deal.pk)
            review_eligibility(deal, user)
            review = Review(item_request=deal, rating=rating, comment=comment.strip())
            review.full_clean()
            review.save()
            return review
    except IntegrityError as exc:
        raise ValidationError('Transaksi ini sudah memiliki ulasan.') from exc


def _review_author(review, user):
    require_user(user)
    if review.item_request.requester_id != user.pk:
        raise PermissionDenied('Hanya penulis yang boleh mengubah atau menghapus ulasan.')


@transaction.atomic
def update_review(review, user, *, rating, comment):
    review = Review.objects.select_for_update().select_related('item_request').get(pk=review.pk)
    _review_author(review, user)
    review.rating, review.comment = rating, comment.strip()
    review.full_clean()
    review.save(update_fields=['rating', 'comment', 'updated_at'])
    return review


@transaction.atomic
def delete_review(review, user):
    review = Review.objects.select_for_update().select_related('item_request').get(pk=review.pk)
    _review_author(review, user)
    review.delete()


def rating_summary(owner):
    return Review.objects.filter(item_request__item__owner=owner).aggregate(average=Avg('rating'), count=Count('pk'))


def create_report(user, *, category, description, target_item=None, target_user=None):
    require_user(user)
    try:
        with transaction.atomic():
            # Serialize creation per reporter, including reports for different targets.
            get_user_model().objects.select_for_update().get(pk=user.pk)
            if bool(target_item) == bool(target_user):
                raise ValidationError('Pilih tepat satu target laporan.')
            if target_item:
                target_item = Item.all_objects.get(pk=target_item.pk)
                if target_item.owner_id == user.pk:
                    raise PermissionDenied('Tidak dapat melaporkan barang sendiri.')
                if target_item.is_deleted:
                    raise ValidationError('Barang sudah dihapus. Laporan baru tidak dapat dibuat.')
            elif target_user.pk == user.pk:
                raise PermissionDenied('Tidak dapat melaporkan diri sendiri.')
            if Report.objects.filter(reporter=user, created_at__gte=timezone.now()-timedelta(hours=1)).count() >= 5:
                raise ValidationError('Maksimal 5 laporan per jam. Coba lagi nanti.')
            report = Report(reporter=user, target_item=target_item, target_user=target_user,
                            category=category, description=description.strip())
            report.full_clean()
            report.save()
            return report
    except IntegrityError as exc:
        raise ValidationError('Kamu sudah memiliki laporan aktif untuk target ini.') from exc


def _pending_reporter(report, user):
    require_user(user)
    if report.reporter_id != user.pk:
        raise PermissionDenied('Laporan ini bukan milikmu.')
    if report.status != Report.Status.PENDING:
        raise ValidationError('Pemeriksaan sudah dimulai; laporan tidak dapat diubah atau dihapus.')


@transaction.atomic
def update_report(report, user, *, category, description):
    report = Report.objects.select_for_update().get(pk=report.pk)
    _pending_reporter(report, user)
    report.category, report.description = category, description.strip()
    report.full_clean()
    report.save(update_fields=['category', 'description', 'updated_at'])
    return report


@transaction.atomic
def delete_report(report, user):
    report = Report.objects.select_for_update().get(pk=report.pk)
    _pending_reporter(report, user)
    report.delete()
