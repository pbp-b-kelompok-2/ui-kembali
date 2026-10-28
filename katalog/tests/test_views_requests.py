from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from katalog.models import Item, ItemRequest

from .test_models import make_item
from .test_views_crud import HX, toast

User = get_user_model()


class RequestViewTestCase(TestCase):
    def setUp(self):
        cache.clear()  # rate-limit counters live in the cache
        self.owner = User.objects.create_user("pemilik", password="pw")
        self.alice = User.objects.create_user("alice", password="pw")
        self.bob = User.objects.create_user("bob", password="pw")
        self.item = make_item(self.owner)


class RequestCreateViewTests(RequestViewTestCase):
    def url(self, item=None):
        return reverse("katalog:request_create", args=[(item or self.item).pk])

    def test_anonymous_is_sent_to_login(self):
        response = self.client.post(self.url(), {"message": "Mau"}, **HX)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("auth_ssoui:login"), response["Location"])
        self.assertFalse(ItemRequest.objects.exists())

    def test_get_is_not_allowed(self):
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get(self.url()).status_code, 405)

    def test_creates_request_and_returns_the_panel(self):
        self.client.force_login(self.alice)
        response = self.client.post(self.url(), {"message": "Untuk kos."}, **HX)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "katalog/_request_panel.html")
        self.assertEqual(toast(response)["level"], "success")
        req = ItemRequest.objects.get()
        self.assertEqual((req.requester, req.message), (self.alice, "Untuk kos."))
        # The panel now shows the pending state with a cancel button.
        self.assertContains(response, "Menunggu")
        self.assertContains(response, reverse("katalog:request_cancel", args=[req.pk]))

    def test_message_is_stripped_of_html(self):
        self.client.force_login(self.alice)
        self.client.post(self.url(), {"message": "<b>Butuh</b> untuk kos"}, **HX)
        self.assertEqual(ItemRequest.objects.get().message, "Butuh untuk kos")

    def test_owner_cannot_request_own_item(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.url(), {}, **HX)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(ItemRequest.objects.exists())

    def test_booked_item_gets_409_toast(self):
        self.item.status = Item.Status.DIPESAN
        self.item.save()
        self.client.force_login(self.alice)
        response = self.client.post(self.url(), {}, **HX)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(toast(response)["level"], "error")

    def test_duplicate_gets_409_toast(self):
        self.client.force_login(self.alice)
        self.client.post(self.url(), {}, **HX)
        response = self.client.post(self.url(), {}, **HX)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(ItemRequest.objects.count(), 1)

    def test_deleted_item_is_404(self):
        self.item.soft_delete()
        self.client.force_login(self.alice)
        self.assertEqual(self.client.post(self.url(), {}, **HX).status_code, 404)

    def test_rate_limited_after_ten_posts_a_minute(self):
        self.client.force_login(self.alice)
        items = [make_item(self.owner, name=f"Barang {i}") for i in range(11)]
        for item in items[:10]:
            self.assertEqual(self.client.post(self.url(item), {}, **HX).status_code, 200)
        response = self.client.post(self.url(items[10]), {}, **HX)
        self.assertEqual(response.status_code, 429)


class DetailRequestPanelTests(RequestViewTestCase):
    def detail(self):
        return self.client.get(reverse("katalog:item_detail", args=[self.item.pk]))

    def test_other_user_sees_the_request_form(self):
        self.client.force_login(self.alice)
        response = self.detail()
        self.assertContains(response, reverse("katalog:request_create", args=[self.item.pk]))
        self.assertContains(response, "Kirim pengajuan adopsi")

    def test_requester_sees_their_pending_request(self):
        ItemRequest.objects.create(item=self.item, requester=self.alice, message="Halo")
        self.client.force_login(self.alice)
        response = self.detail()
        self.assertContains(response, "Menunggu")
        self.assertNotContains(response, "Kirim pengajuan")

    def test_booked_item_shows_no_form(self):
        req = ItemRequest.objects.create(item=self.item, requester=self.bob)
        req.status = ItemRequest.Status.DITERIMA
        req.save()
        self.item.status = Item.Status.DIPESAN
        self.item.save()
        self.client.force_login(self.alice)
        response = self.detail()
        self.assertNotContains(response, "Kirim pengajuan")
        self.assertContains(response, "sudah dipesan")


class RequestsPageTests(RequestViewTestCase):
    url = reverse("katalog:requests_page")

    def setUp(self):
        super().setUp()
        self.incoming = ItemRequest.objects.create(item=self.item, requester=self.alice, message="Butuh meja")
        alice_item = make_item(self.alice, name="Rak buku Alice")
        self.outgoing = ItemRequest.objects.create(item=alice_item, requester=self.owner, message="Mau raknya")

    def test_login_required(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_incoming_tab_lists_requests_on_my_items(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Butuh meja")
        self.assertNotContains(response, "Mau raknya")
        self.assertContains(response, reverse("katalog:request_accept", args=[self.incoming.pk]))

    def test_outgoing_tab_lists_my_requests(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.url, {"tab": "keluar"})
        self.assertContains(response, "Mau raknya")
        self.assertNotContains(response, "Butuh meja")
        self.assertContains(response, reverse("katalog:request_cancel", args=[self.outgoing.pk]))

    def test_status_filter_on_incoming(self):
        self.incoming.status = ItemRequest.Status.DITERIMA
        self.incoming.save()
        self.client.force_login(self.owner)
        pending = self.client.get(self.url, {"status": "ditinjau"})
        accepted = self.client.get(self.url, {"status": "disetujui"})
        self.assertNotContains(pending, "Butuh meja")
        self.assertContains(accepted, "Butuh meja")

    def test_query_count_does_not_grow_with_rows(self):
        self.client.force_login(self.owner)
        with CaptureQueriesContext(connection) as one_row:
            self.client.get(self.url)
        for i in range(5):
            user = User.objects.create_user(f"peminat{i}", password="pw")
            ItemRequest.objects.create(item=self.item, requester=user, message=f"Pesan {i}")
        with CaptureQueriesContext(connection) as six_rows:
            self.client.get(self.url)
        self.assertEqual(len(one_row), len(six_rows))


class RequestActionTests(RequestViewTestCase):
    def setUp(self):
        super().setUp()
        self.req_a = ItemRequest.objects.create(item=self.item, requester=self.alice)
        self.req_b = ItemRequest.objects.create(item=self.item, requester=self.bob)

    def act(self, req, action, **data):
        url = reverse(f"katalog:request_{action}", args=[req.pk])
        return self.client.post(url, data, **HX)

    def refresh(self, *objs):
        for obj in objs:
            obj.refresh_from_db()

    def test_owner_accepts_books_item_and_rejects_the_others(self):
        self.client.force_login(self.owner)
        response = self.act(self.req_a, "accept")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["HX-Refresh"], "true")
        self.refresh(self.req_a, self.req_b, self.item)
        self.assertEqual(self.req_a.status, ItemRequest.Status.DITERIMA)
        self.assertEqual(self.req_b.status, ItemRequest.Status.DITOLAK)
        self.assertEqual(self.item.status, Item.Status.DIPESAN)

    def test_accept_toast_shows_after_the_reload(self):
        self.client.force_login(self.owner)
        self.act(self.req_a, "accept")
        page = self.client.get(reverse("katalog:requests_page"))
        self.assertContains(page, "Permintaan diterima.")

    def test_requester_cannot_accept(self):
        self.client.force_login(self.alice)
        self.assertEqual(self.act(self.req_a, "accept").status_code, 404)
        self.refresh(self.req_a)
        self.assertEqual(self.req_a.status, ItemRequest.Status.PENDING)

    def test_cannot_accept_a_rejected_request(self):
        self.client.force_login(self.owner)
        self.act(self.req_a, "reject")
        self.assertEqual(self.act(self.req_a, "accept").status_code, 404)

    def test_owner_rejects_and_gets_the_row(self):
        self.client.force_login(self.owner)
        response = self.act(self.req_a, "reject")
        self.assertTemplateUsed(response, "katalog/_request_row.html")
        self.assertEqual(toast(response)["level"], "success")
        self.refresh(self.req_a)
        self.assertEqual(self.req_a.status, ItemRequest.Status.DITOLAK)

    def test_stranger_gets_404(self):
        stranger = User.objects.create_user("asing", password="pw")
        self.client.force_login(stranger)
        self.assertEqual(self.act(self.req_a, "reject").status_code, 404)

    def test_requester_cancels(self):
        self.client.force_login(self.alice)
        response = self.act(self.req_a, "cancel")
        self.assertEqual(response.status_code, 200)
        self.refresh(self.req_a)
        self.assertEqual(self.req_a.status, ItemRequest.Status.DIBATALKAN)

    def test_cancelling_the_accepted_request_frees_the_item(self):
        self.client.force_login(self.owner)
        self.act(self.req_a, "accept")
        self.client.force_login(self.alice)
        self.act(self.req_a, "cancel")
        self.refresh(self.item)
        self.assertEqual(self.item.status, Item.Status.TERSEDIA)

    def test_owner_cannot_cancel_someone_elses_request(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.act(self.req_a, "cancel").status_code, 404)

    def test_cancel_from_detail_returns_the_panel(self):
        self.client.force_login(self.alice)
        response = self.act(self.req_a, "cancel", from_detail="1")
        self.assertTemplateUsed(response, "katalog/_request_panel.html")
        self.assertContains(response, "Kirim pengajuan")

    def test_complete_finishes_request_and_item(self):
        self.client.force_login(self.owner)
        self.act(self.req_a, "accept")
        response = self.act(self.req_a, "complete")
        self.assertTemplateUsed(response, "katalog/_request_row.html")
        self.refresh(self.req_a, self.item)
        self.assertEqual(self.req_a.status, ItemRequest.Status.SELESAI)
        self.assertEqual(self.item.status, Item.Status.SELESAI)

    def test_only_an_accepted_request_can_be_completed(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.act(self.req_a, "complete").status_code, 404)

    def test_get_is_not_allowed(self):
        self.client.force_login(self.owner)
        url = reverse("katalog:request_accept", args=[self.req_a.pk])
        self.assertEqual(self.client.get(url).status_code, 405)


class MyItemsTests(RequestViewTestCase):
    url = reverse("katalog:my_items")

    def setUp(self):
        super().setUp()
        self.deleted = make_item(self.owner, name="Kipas rusak")
        self.deleted.soft_delete()
        make_item(self.alice, name="Barang Alice")

    def test_login_required(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_lists_only_my_active_items(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        self.assertContains(response, "Meja belajar")
        self.assertNotContains(response, "Kipas rusak")
        self.assertNotContains(response, "Barang Alice")

    def test_deleted_tab_lists_my_deleted_items(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.url, {"tab": "terhapus"})
        self.assertContains(response, "Kipas rusak")
        self.assertNotContains(response, "Meja belajar")


class BulkActionTests(RequestViewTestCase):
    url = reverse("katalog:bulk_action")

    def setUp(self):
        super().setUp()
        self.second = make_item(self.owner, name="Kipas angin")
        self.foreign = make_item(self.alice, name="Barang Alice")
        self.client.force_login(self.owner)

    def bulk(self, action, items, **extra):
        data = {"action": action, "ids": [str(i.pk) for i in items], **extra}
        return self.client.post(self.url, data, **HX)

    def test_bulk_delete_only_touches_my_items(self):
        response = self.bulk("delete", [self.item, self.second, self.foreign])
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "katalog/_my_items_table.html")
        self.assertIn("2", toast(response)["msg"])
        self.assertFalse(Item.objects.filter(owner=self.owner).exists())
        self.assertTrue(Item.objects.filter(pk=self.foreign.pk).exists())

    def test_bulk_done_marks_items_selesai(self):
        self.bulk("done", [self.item])
        self.item.refresh_from_db()
        self.second.refresh_from_db()
        self.assertEqual(self.item.status, Item.Status.SELESAI)
        self.assertEqual(self.second.status, Item.Status.TERSEDIA)

    def test_bulk_done_closes_open_requests(self):
        accepted = ItemRequest.objects.create(
            item=self.item, requester=self.alice, status=ItemRequest.Status.DITERIMA
        )
        waiting = ItemRequest.objects.create(item=self.item, requester=self.bob)
        self.bulk("done", [self.item])
        accepted.refresh_from_db()
        waiting.refresh_from_db()
        self.assertEqual(accepted.status, ItemRequest.Status.SELESAI)
        self.assertEqual(waiting.status, ItemRequest.Status.DITOLAK)

    def test_bulk_restore_brings_deleted_items_back(self):
        self.item.soft_delete()
        response = self.bulk("restore", [self.item], tab="terhapus")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Item.objects.filter(pk=self.item.pk).exists())

    def test_unknown_action_is_400(self):
        response = self.bulk("hapus_semua", [self.item])
        self.assertEqual(response.status_code, 400)

    def test_nothing_selected_is_400(self):
        response = self.bulk("delete", [])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(toast(response)["level"], "error")

    def test_tampered_ids_are_400(self):
        response = self.client.post(
            self.url, {"action": "delete", "ids": ["bukan-uuid", str(self.item.pk)]}, **HX
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(Item.objects.filter(pk=self.item.pk).exists())

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
