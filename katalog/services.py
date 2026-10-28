"""Request lifecycle rules, kept out of the views so every entry point
(request page, detail panel, bulk actions) follows the same rules.

Every transition locks the item row first (select_for_update), then re-reads
the request. All transitions of one item therefore run one after another, so
two owners' tabs can't both accept a request for the same item.
"""

from contextlib import contextmanager

from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.html import strip_tags

from .models import Item, ItemRequest

PENDING = ItemRequest.Status.PENDING
DITERIMA = ItemRequest.Status.DITERIMA


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


@contextmanager
def _transition(req):
    with transaction.atomic():
        item = Item.all_objects.select_for_update().get(pk=req.item_id)
        req.refresh_from_db(fields=["status"])
        req.item = item
        yield item


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


def accept_request(req, user):
    """Accept `req`, book the item and reject the other pending requests.

    Returns the rejected requests so the view can update their rows too.
    """
    with _transition(req) as item:
        _check_owner(req, user)
        _check_status(req, PENDING)
        _set_status(req, DITERIMA)
        others = list(
            item.requests.filter(status=PENDING)
            .exclude(pk=req.pk)
            .select_related("item", "requester")
        )
        ItemRequest.objects.filter(pk__in=[o.pk for o in others]).update(
            status=ItemRequest.Status.DITOLAK, updated_at=timezone.now()
        )
        for other in others:
            other.status = ItemRequest.Status.DITOLAK
        _set_status(item, Item.Status.DIPESAN)
    return others


def reject_request(req, user):
    with _transition(req):
        _check_owner(req, user)
        _check_status(req, PENDING)
        _set_status(req, ItemRequest.Status.DITOLAK)


def cancel_request(req, user):
    with _transition(req) as item:
        if req.requester_id != user.id:
            raise RequestError("Hanya pengaju yang bisa membatalkan permintaan.", 403)
        _check_status(req, PENDING, DITERIMA)
        was_accepted = req.status == DITERIMA
        _set_status(req, ItemRequest.Status.DIBATALKAN)
        if was_accepted:
            _set_status(item, Item.Status.TERSEDIA)


def complete_request(req, user):
    """The handover happened. Padjri's review module keys off SELESAI."""
    with _transition(req) as item:
        _check_owner(req, user)
        _check_status(req, DITERIMA)
        _set_status(req, ItemRequest.Status.SELESAI)
        _set_status(item, Item.Status.SELESAI)


def mark_items_done(items):
    """Bulk "Tandai selesai": finish the items and close their open requests.

    The accepted request (if any) becomes SELESAI like complete_request does;
    pending ones are rejected so nobody keeps waiting on a finished item.
    Returns the number of items changed.
    """
    now = timezone.now()
    with transaction.atomic():
        ids = list(
            items.select_for_update()
            .exclude(status=Item.Status.SELESAI)
            .values_list("pk", flat=True)
        )
        open_requests = ItemRequest.objects.filter(item_id__in=ids)
        open_requests.filter(status=DITERIMA).update(
            status=ItemRequest.Status.SELESAI, updated_at=now
        )
        open_requests.filter(status=PENDING).update(
            status=ItemRequest.Status.DITOLAK, updated_at=now
        )
        return Item.all_objects.filter(pk__in=ids).update(
            status=Item.Status.SELESAI, updated_at=now
        )
