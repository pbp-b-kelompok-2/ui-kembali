"""Business rules shared by HTTP views and admin. Mutations reload locked rows."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from katalog.models import ItemRequest
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
