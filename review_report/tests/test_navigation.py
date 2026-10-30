from django.urls import reverse
from auth_ssoui.models import Profile
from .base import ModuleCase


class ModuleNavigationTests(ModuleCase):
    def test_entry_point_links_all_personal_sections_and_requires_login(self):
        url = reverse('review_report:home')
        self.assertEqual(url, '/review-report/')
        self.assertEqual(self.client.get(url).status_code, 302)
        response = self.client.get(url, HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 204)
        self.assertIn('/auth/login/', response['HX-Redirect'])
        Profile.objects.create(user=self.buyer, nama='Pembeli UI', is_complete=True)
        self.client.force_login(self.buyer)
        response = self.client.get(url)
        self.assertContains(response, f'href="{url}"')
        for name in ('my_reviews', 'my_reports', 'transactions'):
            self.assertContains(response, reverse('review_report:' + name))

    def test_secondary_navigation_does_not_repeat_main_navigation(self):
        self.client.force_login(self.buyer)
        for name in ('home', 'my_reviews', 'my_reports', 'transactions'):
            response = self.client.get(reverse('review_report:' + name))
            nav = response.content.decode().split('aria-label="Ulasan dan laporan"', 1)[1].split('</nav>', 1)[0]
            self.assertIn('Ulasan Saya', nav)
            self.assertIn('Laporan Saya', nav)
            for duplicate in ('Ulasan &amp; Laporan', 'Jelajahi', 'Riwayat Transaksi'):
                self.assertNotIn(duplicate, nav)
