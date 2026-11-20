import uuid
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from katalog.models import Item, ItemRequest

User = get_user_model()


def make_item(owner, **overrides):
    data = {
        "name": "Buku Kalkulus",
        "description": "Edisi 9, masih mulus tanpa coretan.",
        "category": Item.Category.BUKU,
        "condition": Item.Condition.BAIK,
        "location_name": "Perpustakaan UI",
        "contact": "0812345678",
        "latitude": -6.36,
        "longitude": 106.83,
    }
    data.update(overrides)
    return Item.objects.create(owner=owner, **data)


def png_upload(name="x.png", size=(20, 20)):
    buffer = BytesIO()
    Image.new("RGB", size, "red").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


class ItemAPITest(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="test-password")
        self.other = User.objects.create_user(username="other", password="test-password")
        self.item = make_item(self.owner)
        self.list_url = reverse("api:item-list")
        self.detail_url = reverse("api:item-detail", args=[self.item.id])
        self.request_url = reverse("api:item-request", args=[self.item.id])
        self.payload = {
            "name": "Kursi Belajar",
            "description": "Kursi kayu, kuat dan nyaman dipakai.",
            "category": "PERABOT",
            "condition": "BAIK",
            "location_name": "Margonda",
            "transaction_type": "ADOPSI",
            "contact": "0811111111",
        }

    # --- read ---------------------------------------------------------------

    def test_public_list_hides_contact(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        row = response.data["results"][0]
        self.assertEqual(row["id"], str(self.item.id))
        self.assertNotIn("contact", row)
        self.assertFalse(row["is_owner"])

    def test_logged_in_user_sees_contact_and_exact_coordinates(self):
        self.item.latitude = -6.361234
        self.item.save()
        self.client.force_authenticate(user=self.other)
        row = self.client.get(self.list_url).data["results"][0]
        self.assertEqual(row["contact"], "0812345678")
        self.assertEqual(row["latitude"], -6.361234)

    def test_guest_gets_rounded_coordinates(self):
        self.item.latitude = -6.361234
        self.item.save()
        row = self.client.get(self.list_url).data["results"][0]
        self.assertEqual(row["latitude"], -6.361)

    def test_list_uses_catalog_filters(self):
        make_item(self.owner, name="Setrika Listrik", category=Item.Category.ELEKTRONIK)
        response = self.client.get(self.list_url, {"category": "ELEKTRONIK"})
        self.assertEqual([r["name"] for r in response.data["results"]], ["Setrika Listrik"])
        response = self.client.get(self.list_url, {"q": "tidak-ada"})
        self.assertEqual(response.data["results"], [])

    def test_detail_and_missing_and_soft_deleted(self):
        self.assertEqual(self.client.get(self.detail_url).status_code, status.HTTP_200_OK)
        missing = reverse("api:item-detail", args=[uuid.uuid4()])
        self.assertEqual(self.client.get(missing).status_code, status.HTTP_404_NOT_FOUND)
        self.item.soft_delete()
        self.assertEqual(self.client.get(self.detail_url).status_code, status.HTTP_404_NOT_FOUND)

    def test_my_items_requires_login_and_lists_only_own(self):
        make_item(self.other, name="Milik Orang Lain")
        self.assertEqual(
            self.client.get(reverse("api:item-mine")).status_code, status.HTTP_403_FORBIDDEN,
        )
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(reverse("api:item-mine"))
        self.assertEqual([r["name"] for r in response.data["results"]], ["Buku Kalkulus"])

    # --- create -------------------------------------------------------------

    def test_guest_cannot_create(self):
        response = self.client.post(self.list_url, self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Item.objects.count(), 1)

    def test_create_sets_owner_status_and_geocodes(self):
        self.client.force_authenticate(user=self.other)
        response = self.client.post(
            self.list_url,
            {**self.payload, "owner": "owner", "status": "SELESAI", "latitude": 1},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        item = Item.objects.get(pk=response.data["id"])
        self.assertEqual(item.owner, self.other)
        self.assertEqual(item.status, Item.Status.TERSEDIA)
        self.assertAlmostEqual(item.latitude, -6.3730, places=3)  # "Margonda" built-in place

    def test_create_with_photo_upload(self):
        self.client.force_authenticate(user=self.other)
        response = self.client.post(
            self.list_url, {**self.payload, "photo": png_upload()}, format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertTrue(response.data["photo_url"].startswith("http"))
        Item.objects.get(pk=response.data["id"]).photo.delete(save=False)

    def test_validation_errors(self):
        self.client.force_authenticate(user=self.other)
        cases = [
            ({"name": "<b></b>"}, "name"),
            ({"description": "pendek"}, "description"),
            ({"category": "TIDAK-ADA"}, "category"),
            ({"transaction_type": "JUAL"}, "price"),
            ({"transaction_type": "ADOPSI", "price": 5000}, "price"),
            ({"photo": SimpleUploadedFile("x.png", b"bukan gambar", "image/png")}, "photo"),
        ]
        for changes, field in cases:
            fmt = "multipart" if "photo" in changes else "json"
            response = self.client.post(self.list_url, {**self.payload, **changes}, format=fmt)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, changes)
            self.assertIn(field, response.data)
        self.assertEqual(Item.objects.count(), 1)

    def test_html_is_stripped_from_input(self):
        self.client.force_authenticate(user=self.other)
        response = self.client.post(
            self.list_url, {**self.payload, "name": "<script>x</script>Meja"}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("<", response.data["name"])

    # --- update / delete ----------------------------------------------------

    def test_only_owner_can_patch_and_delete(self):
        for user in (None, self.other):
            self.client.force_authenticate(user=user)
            self.assertEqual(
                self.client.patch(self.detail_url, {"name": "Diubah"}, format="json").status_code,
                status.HTTP_403_FORBIDDEN,
            )
            self.assertEqual(self.client.delete(self.detail_url).status_code, status.HTTP_403_FORBIDDEN)
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, "Buku Kalkulus")
        self.assertFalse(self.item.is_deleted)

    def test_owner_patch_keeps_other_fields_and_cannot_set_status(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.patch(
            self.detail_url, {"name": "Buku Baru", "status": "SELESAI"}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, "Buku Baru")
        self.assertEqual(self.item.contact, "0812345678")
        self.assertEqual(self.item.status, Item.Status.TERSEDIA)

    def test_put_requires_all_required_fields(self):
        self.client.force_authenticate(user=self.owner)
        self.assertEqual(
            self.client.put(self.detail_url, {"name": "Saja"}, format="json").status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.put(self.detail_url, self.payload, format="json").status_code,
            status.HTTP_200_OK,
        )

    def test_patch_price_rules_use_stored_transaction_type(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.patch(self.detail_url, {"price": 1000}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("price", response.data)

    def test_delete_is_a_soft_delete(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(response.content, b"")
        self.assertTrue(Item.all_objects.get(pk=self.item.pk).is_deleted)

    def test_wrong_method(self):
        self.client.force_authenticate(user=self.owner)
        self.assertEqual(
            self.client.delete(self.list_url).status_code, status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    # --- request ("ajukan") -------------------------------------------------

    def test_request_requires_login(self):
        self.assertEqual(self.client.post(self.request_url).status_code, status.HTTP_403_FORBIDDEN)

    def test_request_flow_and_conflicts(self):
        self.client.force_authenticate(user=self.other)
        response = self.client.post(self.request_url, {"message": "<i>Mau dong</i>"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["message"], "Mau dong")
        self.assertEqual(response.data["status"], ItemRequest.Status.PENDING)
        self.assertEqual(self.client.post(self.request_url).status_code, status.HTTP_409_CONFLICT)
        self.item.status = Item.Status.DIPESAN
        self.item.save()
        third = User.objects.create_user(username="third", password="test-password")
        self.client.force_authenticate(user=third)
        self.assertEqual(self.client.post(self.request_url).status_code, status.HTTP_409_CONFLICT)

    def test_owner_cannot_request_own_item(self):
        self.client.force_authenticate(user=self.owner)
        self.assertEqual(self.client.post(self.request_url).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(ItemRequest.objects.count(), 0)

    # --- transactions (riwayat transaksi) ----------------------------------

    def test_transactions_require_login(self):
        url = reverse("api:transaction-list")
        self.assertEqual(self.client.get(url).status_code, status.HTTP_403_FORBIDDEN)

    def test_transactions_show_both_roles_and_hide_strangers(self):
        free = make_item(self.owner, name="Lampu Belajar", transaction_type="ADOPSI")
        mine = ItemRequest.objects.create(item=self.item, requester=self.other)
        theirs = ItemRequest.objects.create(item=free, requester=self.other)
        seller = User.objects.create_user(username="seller", password="test-password")
        buyer = User.objects.create_user(username="buyer", password="test-password")
        ItemRequest.objects.create(item=make_item(seller, name="Bukan Urusan"), requester=buyer)

        self.client.force_authenticate(user=self.other)
        rows = {r["id"]: r for r in self.client.get(reverse("api:transaction-list")).data["results"]}
        self.assertEqual(set(rows), {str(mine.id), str(theirs.id)})
        self.assertEqual(rows[str(mine.id)]["role"], "requester")
        self.assertEqual(rows[str(mine.id)]["counterpart"], "owner")
        self.assertEqual(rows[str(mine.id)]["status_label"], "Menunggu")
        self.assertEqual(rows[str(mine.id)]["item"]["name"], "Buku Kalkulus")

        self.client.force_authenticate(user=self.owner)
        rows = self.client.get(reverse("api:transaction-list")).data["results"]
        self.assertEqual({r["role"] for r in rows}, {"owner"})
        self.assertEqual({r["counterpart"] for r in rows}, {"other"})

    def test_transactions_filter_by_offer_type(self):
        free = make_item(self.owner, name="Lampu Belajar", transaction_type="ADOPSI")
        sale = make_item(self.owner, name="Kipas", transaction_type="JUAL", price=85000)
        ItemRequest.objects.create(item=free, requester=self.other)
        ItemRequest.objects.create(item=sale, requester=self.other)
        self.client.force_authenticate(user=self.other)
        url = reverse("api:transaction-list")

        def names(query):
            return [r["item"]["name"] for r in self.client.get(url, query).data["results"]]

        self.assertEqual(names({"type": "ADOPSI"}), ["Lampu Belajar"])
        self.assertEqual(names({"type": "JUAL"}), ["Kipas"])
        self.assertEqual(len(names({})), 2)

    # --- CSRF (session auth) -----------------------------------------------

    def test_session_write_without_csrf_is_rejected(self):
        client = APIClient(enforce_csrf_checks=True)
        self.assertTrue(client.login(username="owner", password="test-password"))
        response = client.post(self.list_url, self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Item.objects.count(), 1)

    def test_session_write_with_csrf_succeeds(self):
        client = APIClient(enforce_csrf_checks=True)
        client.login(username="owner", password="test-password")
        client.get(self.list_url, HTTP_ACCEPT="text/html")  # Browsable API sets the cookie
        token = client.cookies["csrftoken"].value
        response = client.post(
            self.list_url, self.payload, format="json", HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
