from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from katalog.models import Item, ItemRequest
from katalog.views import PAGE_SIZE

from .test_models import make_item

User = get_user_model()


def get_grid(client, params=None):
    """What the filter form gets: the catalog URL, asked for by HTMX."""
    return client.get(reverse("katalog:catalog"), params or {}, HTTP_HX_REQUEST="true")


class CatalogPageTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("pemilik", password="pw")

    def test_catalog_page_renders_full_page_with_grid(self):
        make_item(self.owner, name="Kipas angin")
        response = self.client.get(reverse("katalog:catalog"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "katalog/catalog.html")
        self.assertTemplateUsed(response, "katalog/_item_grid.html")
        self.assertContains(response, 'id="grid"')
        self.assertContains(response, "Kipas angin")

    def test_htmx_request_to_catalog_page_gets_the_partial(self):
        # The filter form hx-gets the page URL itself (so hx-push-url leaves a
        # real, reloadable URL in the address bar); HTMX only wants the grid.
        make_item(self.owner, name="Kipas angin")
        response = get_grid(self.client)
        self.assertTemplateNotUsed(response, "katalog/catalog.html")
        self.assertTemplateUsed(response, "katalog/_item_grid.html")
        self.assertNotContains(response, "<html")
        self.assertContains(response, "Kipas angin")

    def test_htmx_history_restore_gets_the_full_page(self):
        # On a history cache miss HTMX re-fetches the URL and needs the whole page.
        response = self.client.get(
            reverse("katalog:catalog"),
            HTTP_HX_REQUEST="true",
            HTTP_HX_HISTORY_RESTORE_REQUEST="true",
        )
        self.assertTemplateUsed(response, "katalog/catalog.html")

    def test_empty_catalog_shows_empty_state(self):
        response = get_grid(self.client)
        self.assertContains(response, "Belum ada barang")


class CatalogFilterTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("pemilik", password="pw")
        self.kalkulus = make_item(
            self.owner,
            name="Buku Kalkulus Purcell",
            category=Item.Category.BUKU,
            condition=Item.Condition.BAIK,
            transaction_type=Item.TransactionType.JUAL,
            price=55_000,
            location_name="Perpustakaan UI",
        )
        self.ekonomi = make_item(
            self.owner,
            name="Paket Pengantar Ekonomi",
            description="Tiga buku kuliah ekonomi, ada catatan pensil.",
            category=Item.Category.BUKU,
            condition=Item.Condition.LAYAK_PAKAI,
            location_name="Kukusan",
        )
        self.kipas = make_item(
            self.owner,
            name="Kipas angin",
            category=Item.Category.ELEKTRONIK,
            condition=Item.Condition.SEPERTI_BARU,
            transaction_type=Item.TransactionType.JUAL,
            price=120_000,
            location_name="Pondok Cina",
        )

    def names(self, **params):
        response = get_grid(self.client, params)
        self.assertEqual(response.status_code, 200)
        return [item.name for item in response.context["page_obj"]]

    def test_search_matches_name_and_description(self):
        self.assertEqual(self.names(q="kalkulus"), ["Buku Kalkulus Purcell"])
        self.assertEqual(self.names(q="catatan pensil"), ["Paket Pengantar Ekonomi"])

    def test_filter_by_category(self):
        self.assertCountEqual(
            self.names(category="BUKU"),
            ["Buku Kalkulus Purcell", "Paket Pengantar Ekonomi"],
        )

    def test_filter_by_several_conditions(self):
        response = get_grid(self.client, {"condition": ["BAIK", "SEPERTI_BARU"]})
        self.assertCountEqual(
            [i.name for i in response.context["page_obj"]],
            ["Buku Kalkulus Purcell", "Kipas angin"],
        )

    def test_filter_by_transaction_type(self):
        self.assertEqual(self.names(type="ADOPSI"), ["Paket Pengantar Ekonomi"])

    def test_filter_by_location_text(self):
        self.assertEqual(self.names(location="kukusan"), ["Paket Pengantar Ekonomi"])

    def test_price_range_keeps_free_items_under_max(self):
        # A free item costs 0, so it fits any "max price" but never a "min price".
        self.assertCountEqual(
            self.names(max_price=60_000),
            ["Buku Kalkulus Purcell", "Paket Pengantar Ekonomi"],
        )
        self.assertEqual(self.names(min_price=100_000), ["Kipas angin"])

    def test_invalid_filter_values_are_ignored(self):
        self.assertEqual(
            len(self.names(min_price="abc", condition="RUSAK", sort="hack")), 3
        )

    def test_sort_options(self):
        self.assertEqual(
            self.names(sort="price_asc"),
            ["Paket Pengantar Ekonomi", "Buku Kalkulus Purcell", "Kipas angin"],
        )
        self.assertEqual(
            self.names(sort="price_desc"),
            ["Kipas angin", "Buku Kalkulus Purcell", "Paket Pengantar Ekonomi"],
        )
        self.assertEqual(
            self.names(sort="name"),
            ["Buku Kalkulus Purcell", "Kipas angin", "Paket Pengantar Ekonomi"],
        )

    def test_hides_deleted_and_finished_items(self):
        self.kipas.soft_delete()
        Item.objects.filter(pk=self.ekonomi.pk).update(status=Item.Status.SELESAI)
        self.assertEqual(self.names(), ["Buku Kalkulus Purcell"])

    def test_result_count_and_active_filter_chips(self):
        response = get_grid(self.client, {"q": "buku", "category": "BUKU"})
        self.assertContains(response, "2 barang ditemukan")  # name + description match
        self.assertContains(response, "Buku")  # category chip label
        self.assertContains(response, "Hapus semua")

    def test_pending_count_is_annotated(self):
        requester = User.objects.create_user("peminat", password="pw")
        ItemRequest.objects.create(item=self.kipas, requester=requester)
        ItemRequest.objects.create(
            item=self.kipas,
            requester=User.objects.create_user("lain", password="pw"),
            status=ItemRequest.Status.DITOLAK,
        )
        response = get_grid(self.client, {"q": "kipas"})
        self.assertEqual(response.context["page_obj"][0].pending_count, 1)

    def test_list_query_count_is_constant(self):
        # select_related + annotate: adding items must not add queries.
        for i in range(5):
            make_item(self.owner, name=f"Barang {i}")
        with self.assertNumQueries(2):  # count + page
            get_grid(self.client)


class CatalogPaginationTests(TestCase):
    def setUp(self):
        owner = User.objects.create_user("pemilik", password="pw")
        for i in range(PAGE_SIZE + 3):
            make_item(owner, name=f"Barang {i:02d}")

    def test_first_page_is_full_and_links_to_next(self):
        response = get_grid(self.client)
        self.assertEqual(len(response.context["page_obj"]), PAGE_SIZE)
        self.assertContains(response, "page=2")

    def test_out_of_range_page_falls_back_to_last(self):
        response = get_grid(self.client, {"page": 99})
        self.assertEqual(response.context["page_obj"].number, 2)
        self.assertEqual(len(response.context["page_obj"]), 3)

    def test_page_links_keep_the_filters(self):
        response = get_grid(self.client, {"q": "barang"})
        self.assertContains(response, "q=barang&amp;page=2")


class ItemsJsonTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("pemilik", password="pw")
        self.item = make_item(
            self.owner,
            transaction_type=Item.TransactionType.JUAL,
            price=25_000,
        )

    def test_json_list_hides_contact_for_anonymous(self):
        response = self.client.get(reverse("katalog:items_json"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        row = data["results"][0]
        self.assertEqual(row["id"], str(self.item.pk))
        self.assertEqual(row["name"], "Meja belajar")
        self.assertEqual(row["price"], 25_000)
        self.assertEqual(row["owner"], "pemilik")
        self.assertNotIn("contact", row)

    def test_json_list_shows_contact_when_logged_in(self):
        self.client.force_login(User.objects.create_user("tamu", password="pw"))
        row = self.client.get(reverse("katalog:items_json")).json()["results"][0]
        self.assertEqual(row["contact"], "081234567890")

    def test_json_list_uses_the_same_filters(self):
        response = self.client.get(reverse("katalog:items_json"), {"type": "ADOPSI"})
        self.assertEqual(response.json()["count"], 0)


class ItemDetailTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("pemilik", password="pw")
        self.item = make_item(self.owner, name="Buku Campbell Biology")

    def test_detail_page_hides_contact_for_anonymous(self):
        response = self.client.get(reverse("katalog:item_detail", args=[self.item.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "katalog/detail.html")
        self.assertContains(response, "Buku Campbell Biology")
        self.assertNotContains(response, "081234567890")
        self.assertContains(response, "Masuk untuk melihat kontak")

    def test_detail_page_shows_contact_when_logged_in(self):
        self.client.force_login(User.objects.create_user("tamu", password="pw"))
        response = self.client.get(reverse("katalog:item_detail", args=[self.item.pk]))
        self.assertContains(response, "081234567890")

    def test_deleted_item_is_404(self):
        self.item.soft_delete()
        response = self.client.get(reverse("katalog:item_detail", args=[self.item.pk]))
        self.assertEqual(response.status_code, 404)
        response = self.client.get(
            reverse("katalog:item_detail_json", args=[self.item.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_detail_json(self):
        url = reverse("katalog:item_detail_json", args=[self.item.pk])
        data = self.client.get(url).json()
        self.assertEqual(data["name"], "Buku Campbell Biology")
        self.assertEqual(data["condition"], "BAIK")
        self.assertEqual(data["condition_label"], "Baik")
        self.assertNotIn("contact", data)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(url).json()["contact"], "081234567890")

    def test_description_is_escaped(self):
        Item.objects.filter(pk=self.item.pk).update(
            description="<script>alert(1)</script> sisa teks"
        )
        response = self.client.get(reverse("katalog:item_detail", args=[self.item.pk]))
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;")
