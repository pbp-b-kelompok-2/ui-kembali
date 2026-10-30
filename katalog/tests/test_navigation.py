from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from auth_ssoui.models import Profile

User = get_user_model()


class SiteNavigationTests(TestCase):
    def test_lobby_hero_links_to_the_catalog(self):
        response = self.client.get(reverse("main:lobby"))
        # Check the link, not its CSS class, so lobby redesigns don't break this test.
        self.assertContains(response, f'href="{reverse("katalog:catalog")}"')
        self.assertContains(response, "Lihat katalog")

    def test_logged_in_navbar_links_to_katalog_pages(self):
        # The full navbar only shows once the SSO profile is complete.
        user = User.objects.create_user("pemilik", password="pw")
        Profile.objects.create(user=user, nama="Owen Pemilik", is_complete=True)
        self.client.force_login(user)
        response = self.client.get(reverse("katalog:catalog"))
        self.assertContains(response, f'<a href="{reverse("katalog:catalog")}">Jelajahi</a>')
        self.assertContains(response, f'<a href="{reverse("katalog:requests_page")}">Transaksi</a>')
        self.assertContains(response, f'href="{reverse("katalog:catalog")}#pasang"')
        # The header search is a real form that searches the catalog.
        self.assertContains(response, f'action="{reverse("katalog:catalog")}" role="search"')
        self.assertContains(response, "load[location.hash === '#pasang']")
        # Already on the catalog the link only changes the hash, so listen for the click too.
        self.assertContains(response, "click from:.btn-pasang")

    def test_card_buttons_do_not_inherit_the_filter_forms_url_push(self):
        # Otherwise opening the Edit form changes the URL to /edit/, and a
        # refresh there shows the bare form without the site around it.
        response = self.client.get(reverse("katalog:catalog"))
        self.assertContains(response, 'hx-push-url="true" hx-disinherit="hx-push-url"')
