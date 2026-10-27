from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from katalog.models import Item, ItemRequest

from .models import Profile


User = get_user_model()


class ProfileHistoryViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("viewer", password="pw")
        self.owner = User.objects.create_user("owner", password="pw")
        Profile.objects.create(
            user=self.user,
            nama="Viewer User",
            faculty="Ilmu Komputer",
            angkatan="2023",
            is_complete=True,
        )
        Profile.objects.create(
            user=self.owner,
            nama="Owner User",
            faculty="Ilmu Komputer",
            angkatan="2022",
            is_complete=True,
        )

        for index in range(4):
            item = Item.objects.create(
                owner=self.owner,
                name=f"Barang {index}",
                description="Barang bekas yang masih layak dipakai.",
                category=Item.Category.PERABOT,
                condition=Item.Condition.BAIK,
                location_name="Kukusan",
                contact="081234567890",
            )
            ItemRequest.objects.create(item=item, requester=self.user)

        self.client.force_login(self.user)
        self.url = reverse("auth_ssoui:profile_history")

    def test_profile_page_does_not_render_full_history_at_first(self):
        response = self.client.get(reverse("auth_ssoui:profile"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Semua transaksi")
        self.assertContains(response, "data-history-url")

    def test_history_endpoint_returns_first_page_only(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "profile/components/full_riwayat.html")
        self.assertContains(response, "4 transaksi")
        self.assertContains(response, "Barang 3")
        self.assertContains(response, "Barang 2")
        self.assertContains(response, "Barang 1")
        self.assertNotContains(response, "Barang 0")

    def test_history_endpoint_supports_partial_pagination(self):
        response = self.client.get(self.url, {"page": 2})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Barang 0")
        self.assertNotContains(response, "Barang 3")
