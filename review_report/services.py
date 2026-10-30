"""Business rules shared by HTTP views and admin. Mutations reload locked rows."""
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count
from django.utils import timezone
from katalog.models import Item, ItemRequest
from .models import Review


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


