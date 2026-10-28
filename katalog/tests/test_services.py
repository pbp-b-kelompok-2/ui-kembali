from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from katalog import services
from katalog.models import Item, ItemRequest
from katalog.services import RequestError

from .test_models import make_item

User = get_user_model()


class ServiceTestCase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("pemilik", password="pw")
        self.alice = User.objects.create_user("alice", password="pw")
        self.bob = User.objects.create_user("bob", password="pw")
        self.item = make_item(self.owner)

    def refresh(self, *objs):
        for obj in objs:
            obj.refresh_from_db()


class CreateRequestTests(ServiceTestCase):
    def test_creates_a_pending_request(self):
        req = services.create_request(self.item, self.alice, "Butuh untuk kos.")
        self.assertEqual(req.status, ItemRequest.Status.PENDING)
        self.assertEqual(req.requester, self.alice)
        self.assertEqual(req.message, "Butuh untuk kos.")

    def test_message_is_stripped_of_html(self):
        req = services.create_request(self.item, self.alice, "<b>Halo</b><script>x</script>")
        self.assertNotIn("<", req.message)

    def test_cannot_request_your_own_item(self):
        with self.assertRaises(RequestError) as ctx:
            services.create_request(self.item, self.owner)
        self.assertEqual(ctx.exception.status, 403)

    def test_cannot_request_an_item_that_is_not_available(self):
        self.item.status = Item.Status.DIPESAN
        self.item.save()
        with self.assertRaises(RequestError) as ctx:
            services.create_request(self.item, self.alice)
        self.assertEqual(ctx.exception.status, 409)

    def test_cannot_have_two_pending_requests_for_one_item(self):
        services.create_request(self.item, self.alice)
        with self.assertRaises(RequestError) as ctx:
            services.create_request(self.item, self.alice)
        self.assertEqual(ctx.exception.status, 409)
        self.assertEqual(ItemRequest.objects.count(), 1)

    def test_can_request_again_after_a_rejection(self):
        first = services.create_request(self.item, self.alice)
        services.reject_request(first, self.owner)
        again = services.create_request(self.item, self.alice)
        self.assertEqual(again.status, ItemRequest.Status.PENDING)


class AcceptRequestTests(ServiceTestCase):
    def setUp(self):
        super().setUp()
        self.req_a = services.create_request(self.item, self.alice)
        self.req_b = services.create_request(self.item, self.bob)

    def test_accept_books_the_item_and_rejects_the_others(self):
        rejected = services.accept_request(self.req_a, self.owner)
        self.refresh(self.req_a, self.req_b, self.item)
        self.assertEqual(self.req_a.status, ItemRequest.Status.DITERIMA)
        self.assertEqual(self.req_b.status, ItemRequest.Status.DITOLAK)
        self.assertEqual(self.item.status, Item.Status.DIPESAN)
        # The view uses the returned rows to update them on screen.
        self.assertEqual([r.pk for r in rejected], [self.req_b.pk])

    def test_only_the_owner_can_accept(self):
        with self.assertRaises(RequestError) as ctx:
            services.accept_request(self.req_a, self.alice)
        self.assertEqual(ctx.exception.status, 403)

    def test_only_a_pending_request_can_be_accepted(self):
        services.reject_request(self.req_a, self.owner)
        with self.assertRaises(RequestError) as ctx:
            services.accept_request(self.req_a, self.owner)
        self.assertEqual(ctx.exception.status, 409)

    def test_accept_is_atomic(self):
        # If booking the item fails, the request must not stay DITERIMA.
        with mock.patch.object(Item, "save", side_effect=RuntimeError("db down")):
            with self.assertRaises(RuntimeError):
                services.accept_request(self.req_a, self.owner)
        self.refresh(self.req_a, self.req_b, self.item)
        self.assertEqual(self.req_a.status, ItemRequest.Status.PENDING)
        self.assertEqual(self.req_b.status, ItemRequest.Status.PENDING)
        self.assertEqual(self.item.status, Item.Status.TERSEDIA)


class RejectCancelCompleteTests(ServiceTestCase):
    def setUp(self):
        super().setUp()
        self.req = services.create_request(self.item, self.alice)

    def test_owner_rejects(self):
        services.reject_request(self.req, self.owner)
        self.refresh(self.req)
        self.assertEqual(self.req.status, ItemRequest.Status.DITOLAK)

    def test_requester_cannot_reject(self):
        with self.assertRaises(RequestError) as ctx:
            services.reject_request(self.req, self.alice)
        self.assertEqual(ctx.exception.status, 403)

    def test_requester_cancels_a_pending_request(self):
        services.cancel_request(self.req, self.alice)
        self.refresh(self.req, self.item)
        self.assertEqual(self.req.status, ItemRequest.Status.DIBATALKAN)
        self.assertEqual(self.item.status, Item.Status.TERSEDIA)

    def test_cancelling_the_accepted_request_frees_the_item(self):
        services.accept_request(self.req, self.owner)
        services.cancel_request(self.req, self.alice)
        self.refresh(self.req, self.item)
        self.assertEqual(self.req.status, ItemRequest.Status.DIBATALKAN)
        self.assertEqual(self.item.status, Item.Status.TERSEDIA)

    def test_owner_cannot_cancel_someone_elses_request(self):
        with self.assertRaises(RequestError) as ctx:
            services.cancel_request(self.req, self.owner)
        self.assertEqual(ctx.exception.status, 403)

    def test_a_finished_request_cannot_be_cancelled(self):
        services.reject_request(self.req, self.owner)
        with self.assertRaises(RequestError) as ctx:
            services.cancel_request(self.req, self.alice)
        self.assertEqual(ctx.exception.status, 409)

    def test_complete_finishes_request_and_item(self):
        services.accept_request(self.req, self.owner)
        services.complete_request(self.req, self.owner)
        self.refresh(self.req, self.item)
        self.assertEqual(self.req.status, ItemRequest.Status.SELESAI)
        self.assertEqual(self.item.status, Item.Status.SELESAI)

    def test_only_an_accepted_request_can_be_completed(self):
        with self.assertRaises(RequestError) as ctx:
            services.complete_request(self.req, self.owner)
        self.assertEqual(ctx.exception.status, 409)

    def test_only_the_owner_can_complete(self):
        services.accept_request(self.req, self.owner)
        with self.assertRaises(RequestError) as ctx:
            services.complete_request(self.req, self.alice)
        self.assertEqual(ctx.exception.status, 403)


class MarkItemsDoneTests(ServiceTestCase):
    def test_closes_open_requests_of_finished_items(self):
        accepted = services.create_request(self.item, self.alice)
        services.accept_request(accepted, self.owner)
        other_item = make_item(self.owner, name="Kipas angin")
        pending = services.create_request(other_item, self.bob)

        count = services.mark_items_done(Item.objects.filter(owner=self.owner))

        self.assertEqual(count, 2)
        self.refresh(accepted, pending, self.item, other_item)
        self.assertEqual(self.item.status, Item.Status.SELESAI)
        self.assertEqual(other_item.status, Item.Status.SELESAI)
        # The accepted handover counts as done (Padjri's review hook) …
        self.assertEqual(accepted.status, ItemRequest.Status.SELESAI)
        # … and nobody is left waiting on an item that is gone.
        self.assertEqual(pending.status, ItemRequest.Status.DITOLAK)
