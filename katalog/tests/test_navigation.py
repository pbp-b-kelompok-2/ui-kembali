from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class SiteNavigationTests(TestCase):
    def test_lobby_hero_links_to_the_catalog(self):
        response = self.client.get(reverse("main:lobby"))
        self.assertContains(response, f'href="{reverse("katalog:catalog")}" class="btn btn-ghost"')

    def test_logged_in_navbar_links_to_katalog_pages(self):
        self.client.force_login(User.objects.create_user("pemilik", password="pw"))
        response = self.client.get(reverse("katalog:catalog"))
        self.assertContains(response, f'<a href="{reverse("katalog:catalog")}">Jelajahi</a>')
        self.assertContains(response, f'<a href="{reverse("katalog:requests_page")}">Transaksi</a>')
        self.assertContains(response, f'href="{reverse("katalog:catalog")}#pasang"')
        # The header search is a real form that searches the catalog.
        self.assertContains(response, f'action="{reverse("katalog:catalog")}" role="search"')
        self.assertContains(response, "load[location.hash === '#pasang']")
