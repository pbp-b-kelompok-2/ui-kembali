from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from katalog import services
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
        self.assertIn(reverse("auth_ssoui:login"), response["HX-Redirect"])
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
        self.assertContains(response, reverse("katalog:request_action", args=[req.pk, "cancel"]))

    def test_owner_gets_403_toast(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.url(), {}, **HX)
        self.assertEqual(response.status_code, 403)
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
        services.create_request(self.item, self.alice, "Halo")
        self.client.force_login(self.alice)
        response = self.detail()
        self.assertContains(response, "Menunggu")
        self.assertNotContains(response, "Kirim pengajuan")

    def test_booked_item_shows_no_form(self):
        req = services.create_request(self.item, self.bob)
        services.accept_request(req, self.owner)
        self.client.force_login(self.alice)
        response = self.detail()
        self.assertNotContains(response, "Kirim pengajuan")
        self.assertContains(response, "sudah dipesan")


class RequestsPageTests(RequestViewTestCase):
    url = reverse("katalog:requests_page")

    def setUp(self):
        super().setUp()
        self.incoming = services.create_request(self.item, self.alice, "Butuh meja")
        alice_item = make_item(self.alice, name="Rak buku Alice")
        self.outgoing = services.create_request(alice_item, self.owner, "Mau raknya")

    def test_login_required(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_incoming_tab_lists_requests_on_my_items(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Butuh meja")
        self.assertNotContains(response, "Mau raknya")
        self.assertContains(response, reverse("katalog:request_action", args=[self.incoming.pk, "accept"]))

    def test_outgoing_tab_lists_my_requests(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.url, {"tab": "keluar"})
        self.assertContains(response, "Mau raknya")
        self.assertNotContains(response, "Butuh meja")
        self.assertContains(response, reverse("katalog:request_action", args=[self.outgoing.pk, "cancel"]))

    def test_status_filter_on_incoming(self):
        services.accept_request(self.incoming, self.owner)
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
            services.create_request(self.item, user, f"Pesan {i}")
        with CaptureQueriesContext(connection) as six_rows:
            self.client.get(self.url)
        self.assertEqual(len(one_row), len(six_rows))


class RequestActionTests(RequestViewTestCase):
    def setUp(self):
        super().setUp()
        self.req_a = services.create_request(self.item, self.alice)
        self.req_b = services.create_request(self.item, self.bob)

    def act(self, req, action):
        return self.client.post(
            reverse("katalog:request_action", args=[req.pk, action]), **HX
        )

    def test_owner_accepts_and_sibling_rows_update_out_of_band(self):
        self.client.force_login(self.owner)
        response = self.act(self.req_a, "accept")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "katalog/_request_row.html")
        self.assertContains(response, f'id="request-{self.req_a.pk}"')
        self.assertContains(response, "Disetujui")
        # Bob's row is rejected in the same transaction and swapped too.
        self.assertContains(response, f'id="request-{self.req_b.pk}" hx-swap-oob="outerHTML"')
        self.assertEqual(toast(response)["level"], "success")

    def test_requester_cannot_accept(self):
        self.client.force_login(self.alice)
        response = self.act(self.req_a, "accept")
        self.assertEqual(response.status_code, 403)
        self.req_a.refresh_from_db()
        self.assertEqual(self.req_a.status, ItemRequest.Status.PENDING)

    def test_stranger_gets_404(self):
        stranger = User.objects.create_user("asing", password="pw")
        self.client.force_login(stranger)
        self.assertEqual(self.act(self.req_a, "reject").status_code, 404)

    def test_requester_cancels(self):
        self.client.force_login(self.alice)
        response = self.act(self.req_a, "cancel")
        self.assertEqual(response.status_code, 200)
        self.req_a.refresh_from_db()
        self.assertEqual(self.req_a.status, ItemRequest.Status.DIBATALKAN)

    def test_cancel_from_detail_returns_the_panel(self):
        self.client.force_login(self.alice)
        response = self.client.post(
            reverse("katalog:request_action", args=[self.req_a.pk, "cancel"]),
            {"from_detail": "1"},
            **HX,
        )
        self.assertTemplateUsed(response, "katalog/_request_panel.html")
        self.assertContains(response, "Kirim pengajuan")

    def test_invalid_transition_is_409(self):
        self.client.force_login(self.owner)
        response = self.act(self.req_a, "complete")
        self.assertEqual(response.status_code, 409)

    def test_unknown_action_is_404(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.act(self.req_a, "hapus").status_code, 404)

    def test_get_is_not_allowed(self):
        self.client.force_login(self.owner)
        url = reverse("katalog:request_action", args=[self.req_a.pk, "accept"])
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

    def test_bad_ids_are_ignored(self):
        response = self.client.post(
            self.url, {"action": "delete", "ids": ["bukan-uuid", str(self.item.pk)]}, **HX
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Item.objects.filter(pk=self.item.pk).exists())

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
