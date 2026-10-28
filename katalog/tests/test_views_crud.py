import json

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from katalog.models import Item

from .test_models import make_item

User = get_user_model()
HX = {"HTTP_HX_REQUEST": "true"}

VALID_POST = {
    "name": "Lampu belajar LED",
    "description": "Lampu meja, cahaya putih, kabel masih bagus.",
    "category": Item.Category.ELEKTRONIK,
    "condition": Item.Condition.BAIK,
    "photo_url": "",
    "location_name": "Kukusan",
    "transaction_type": Item.TransactionType.JUAL,
    "price": "35000",
    "contact": "081234567890",
}


def toast(response):
    return json.loads(response["HX-Trigger"])["toast"]


class CrudTestCase(TestCase):
    def setUp(self):
        cache.clear()  # rate-limit counters live in the cache
        self.owner = User.objects.create_user("pemilik", password="pw")
        self.other = User.objects.create_user("orang_lain", password="pw")
        self.item = make_item(self.owner)


class OwnerRequiredTests(CrudTestCase):
    def edit_url(self, pk=None):
        return reverse("katalog:item_update", args=[pk or self.item.pk])

    def test_anonymous_is_sent_to_sso_login(self):
        response = self.client.get(self.edit_url())
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("auth_ssoui:login"), response["Location"])

    def test_missing_item_is_404(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            self.edit_url("00000000-0000-0000-0000-000000000000")
        )
        self.assertEqual(response.status_code, 404)

    def test_non_owner_gets_403_page(self):
        self.client.force_login(self.other)
        response = self.client.get(self.edit_url())
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, "katalog/403.html")

    def test_non_owner_htmx_request_gets_403_toast(self):
        self.client.force_login(self.other)
        response = self.client.get(self.edit_url(), **HX)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(toast(response)["level"], "error")


class ItemCreateTests(CrudTestCase):
    url = reverse("katalog:item_create")

    def setUp(self):
        super().setUp()
        self.client.force_login(self.owner)

    def test_get_returns_the_form_partial(self):
        response = self.client.get(self.url, **HX)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "katalog/_item_form.html")
        self.assertNotContains(response, "<html")

    def test_valid_post_creates_item_and_returns_card(self):
        response = self.client.post(self.url, VALID_POST, **HX)
        self.assertEqual(response.status_code, 200)
        item = Item.objects.get(name="Lampu belajar LED")
        self.assertEqual(item.owner, self.owner)
        self.assertEqual(item.price, 35_000)
        self.assertTemplateUsed(response, "katalog/_item_card.html")
        self.assertContains(response, f'id="item-{item.pk}"')
        self.assertEqual(toast(response)["level"], "success")

    def test_invalid_post_returns_422_form_into_the_modal(self):
        data = {**VALID_POST, "name": "<b>a</b>", "price": ""}
        response = self.client.post(self.url, data, **HX)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response["HX-Retarget"], "#modal-body")
        self.assertTemplateUsed(response, "katalog/_item_form.html")
        self.assertContains(response, "Nama minimal 3 karakter", status_code=422)
        self.assertContains(response, "Harga wajib diisi", status_code=422)
        self.assertFalse(Item.objects.filter(name__contains="a</b>").exists())

    def test_non_htmx_post_redirects_to_detail(self):
        response = self.client.post(self.url, VALID_POST)
        item = Item.objects.get(name="Lampu belajar LED")
        self.assertRedirects(response, reverse("katalog:item_detail", args=[item.pk]))

    def test_rate_limited_after_ten_posts_a_minute(self):
        for i in range(10):
            self.client.post(self.url, {**VALID_POST, "name": f"Barang ke {i}"}, **HX)
        response = self.client.post(self.url, VALID_POST, **HX)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(toast(response)["level"], "error")
        self.assertEqual(Item.objects.filter(owner=self.owner).count(), 11)

    def test_anonymous_cannot_create(self):
        self.client.logout()
        response = self.client.post(self.url, VALID_POST)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Item.objects.filter(name="Lampu belajar LED").exists())


class ItemUpdateTests(CrudTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("katalog:item_update", args=[self.item.pk])

    def test_owner_gets_prefilled_form(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.url, **HX)
        self.assertTemplateUsed(response, "katalog/_item_form.html")
        self.assertContains(response, 'value="Meja belajar"')

    def test_owner_post_updates_and_swaps_the_card(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.url, {**VALID_POST, "name": "Meja lipat"}, **HX)
        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, "Meja lipat")
        self.assertEqual(response["HX-Retarget"], f"#item-{self.item.pk}")
        self.assertEqual(response["HX-Reswap"], "outerHTML")
        self.assertEqual(toast(response)["level"], "success")

    def test_edit_from_detail_page_reloads_the_detail(self):
        self.client.force_login(self.owner)
        data = {**VALID_POST, "from_detail": "1"}
        response = self.client.post(self.url, data, **HX)
        self.assertEqual(
            response["HX-Redirect"], reverse("katalog:item_detail", args=[self.item.pk])
        )

    def test_form_opened_on_detail_page_does_not_target_the_grid(self):
        # The detail page has no #item-list; HTMX would cancel the request.
        self.client.force_login(self.owner)
        response = self.client.get(self.url, {"from_detail": "1"}, **HX)
        self.assertContains(response, 'name="from_detail"')
        self.assertNotContains(response, 'hx-target="#item-list"')

    def test_invalid_post_is_422(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.url, {**VALID_POST, "description": "pendek"}, **HX)
        self.assertEqual(response.status_code, 422)
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, "Meja belajar")

    def test_non_owner_cannot_update(self):
        self.client.force_login(self.other)
        response = self.client.post(self.url, {**VALID_POST, "name": "Diretas"}, **HX)
        self.assertEqual(response.status_code, 403)
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, "Meja belajar")


class ItemDeleteRestoreTests(CrudTestCase):
    def setUp(self):
        super().setUp()
        self.delete_url = reverse("katalog:item_soft_delete", args=[self.item.pk])
        self.restore_url = reverse("katalog:item_restore", args=[self.item.pk])

    def test_delete_requires_post(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.delete_url).status_code, 405)

    def test_owner_soft_deletes_with_undo_toast(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.delete_url, **HX)
        self.assertEqual(response.status_code, 204)
        self.assertTrue(Item.all_objects.get(pk=self.item.pk).is_deleted)
        self.assertFalse(Item.objects.filter(pk=self.item.pk).exists())
        undo = toast(response)
        self.assertEqual(undo["undo"], self.restore_url)
        self.assertEqual(undo["target"], f"#item-{self.item.pk}")

    def test_delete_from_detail_page_redirects_to_catalog(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.delete_url, {"from_detail": "1"}, **HX)
        self.assertEqual(response["HX-Redirect"], reverse("katalog:catalog"))

    def test_non_owner_cannot_delete(self):
        self.client.force_login(self.other)
        response = self.client.post(self.delete_url, **HX)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Item.all_objects.get(pk=self.item.pk).is_deleted)

    def test_owner_restores_and_gets_the_card_back(self):
        self.item.soft_delete()
        self.client.force_login(self.owner)
        response = self.client.post(self.restore_url, **HX)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "katalog/_item_card.html")
        self.assertFalse(Item.all_objects.get(pk=self.item.pk).is_deleted)

    def test_non_owner_cannot_restore(self):
        self.item.soft_delete()
        self.client.force_login(self.other)
        response = self.client.post(self.restore_url, **HX)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Item.all_objects.get(pk=self.item.pk).is_deleted)


class OwnerControlsTests(CrudTestCase):
    def test_owner_sees_edit_and_delete_on_own_card(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("katalog:catalog"))
        self.assertContains(response, reverse("katalog:item_update", args=[self.item.pk]))
        self.assertContains(
            response, reverse("katalog:item_soft_delete", args=[self.item.pk])
        )

    def test_non_owner_and_anonymous_see_no_owner_controls(self):
        edit_url = reverse("katalog:item_update", args=[self.item.pk])
        self.assertNotContains(self.client.get(reverse("katalog:catalog")), edit_url)
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(reverse("katalog:catalog")), edit_url)
        detail = self.client.get(reverse("katalog:item_detail", args=[self.item.pk]))
        self.assertNotContains(detail, edit_url)

    def test_owner_sees_controls_on_detail_page(self):
        self.client.force_login(self.owner)
        detail = self.client.get(reverse("katalog:item_detail", args=[self.item.pk]))
        self.assertContains(detail, reverse("katalog:item_update", args=[self.item.pk]))

    def test_pasang_barang_button(self):
        create_url = reverse("katalog:item_create")
        self.assertNotContains(self.client.get(reverse("katalog:catalog")), create_url)
        self.client.force_login(self.other)
        self.assertContains(self.client.get(reverse("katalog:catalog")), create_url)
