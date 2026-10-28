"""Request lifecycle rules, kept out of the views so every entry point
(request page, detail panel, bulk actions) follows the same rules.

Every transition runs in a transaction and starts with _lock(): it locks the
item row (select_for_update) and re-reads the request. So two owners' tabs
can't both accept a request for the same item.
"""

from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.html import strip_tags

from .models import Item, ItemRequest

PENDING = ItemRequest.Status.PENDING
DITERIMA = ItemRequest.Status.DITERIMA
DITOLAK = ItemRequest.Status.DITOLAK


class RequestError(Exception):
    """A rule was broken. `status` is the HTTP status the view should answer
    with: 403 = not your request/item, 409 = not allowed in the current state."""

    def __init__(self, message, status=409):
        super().__init__(message)
        self.message = message
        self.status = status


def create_request(item, user, message=""):
    if item.owner_id == user.id:
        raise RequestError("Tidak bisa mengajukan barangmu sendiri.", 403)
    if item.status != Item.Status.TERSEDIA:
        raise RequestError("Barang ini sudah tidak tersedia.")
    try:
        # The savepoint keeps an outer transaction usable after the
        # IntegrityError from the unique-pending constraint.
        with transaction.atomic():
            return ItemRequest.objects.create(
                item=item, requester=user, message=strip_tags(message).strip()
            )
    except IntegrityError:
        raise RequestError("Kamu sudah mengajukan barang ini. Tunggu balasan pemilik ya.")


def _lock(req):
    """Lock the request's item and re-read the request's latest status."""
    req.item = Item.all_objects.select_for_update().get(pk=req.item_id)
    req.refresh_from_db(fields=["status"])
    return req.item


def _check_owner(req, user):
    if req.item.owner_id != user.id:
        raise RequestError("Hanya pemilik barang yang bisa melakukan ini.", 403)


def _check_status(req, *allowed):
    if req.status not in allowed:
        raise RequestError(
            f"Permintaan ini sudah {req.get_status_display().lower()}, aksi tidak bisa dilakukan."
        )


def _set_status(obj, status):
    obj.status = status
    obj.save(update_fields=["status", "updated_at"])


@transaction.atomic
def accept_request(req, user):
    """Accept `req`, book the item and reject the other pending requests.

    Returns the rejected requests so the view can update their rows too.
    """
    item = _lock(req)
    _check_owner(req, user)
    _check_status(req, PENDING)
    _set_status(req, DITERIMA)
    others = list(
        item.requests.filter(status=PENDING)
        .exclude(pk=req.pk)
        .select_related("item", "requester")
    )
    for other in others:
        _set_status(other, DITOLAK)
    _set_status(item, Item.Status.DIPESAN)
    return others


@transaction.atomic
def reject_request(req, user):
    _lock(req)
    _check_owner(req, user)
    _check_status(req, PENDING)
    _set_status(req, DITOLAK)


@transaction.atomic
def cancel_request(req, user):
    item = _lock(req)
    if req.requester_id != user.id:
        raise RequestError("Hanya pengaju yang bisa membatalkan permintaan.", 403)
    _check_status(req, PENDING, DITERIMA)
    if req.status == DITERIMA:
        # The item was booked for this requester; free it again.
        _set_status(item, Item.Status.TERSEDIA)
    _set_status(req, ItemRequest.Status.DIBATALKAN)


@transaction.atomic
def complete_request(req, user):
    """The handover happened. Padjri's review module keys off SELESAI."""
    item = _lock(req)
    _check_owner(req, user)
    _check_status(req, DITERIMA)
    _set_status(req, ItemRequest.Status.SELESAI)
    _set_status(item, Item.Status.SELESAI)


@transaction.atomic
def mark_items_done(items):
    """Bulk "Tandai selesai": finish the items and close their open requests.

    The accepted request (if any) becomes SELESAI like complete_request does;
    pending ones are rejected so nobody keeps waiting on a finished item.
    Returns the number of items changed.
    """
    now = timezone.now()
    ids = list(
        items.select_for_update()
        .exclude(status=Item.Status.SELESAI)
        .values_list("pk", flat=True)
    )
    open_requests = ItemRequest.objects.filter(item_id__in=ids)
    open_requests.filter(status=DITERIMA).update(
        status=ItemRequest.Status.SELESAI, updated_at=now
    )
    open_requests.filter(status=PENDING).update(status=DITOLAK, updated_at=now)
    return Item.all_objects.filter(pk__in=ids).update(
        status=Item.Status.SELESAI, updated_at=now
    )
