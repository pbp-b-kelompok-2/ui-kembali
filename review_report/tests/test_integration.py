from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.urls import reverse
from auth_ssoui.models import Profile
from katalog.models import ItemRequest
from review_report import services
from .base import ModuleCase


class IntegrationTests(ModuleCase):
    def test_completed_request_links_from_request_center_and_profile_history(self):
        Profile.objects.create(user=self.buyer, nama='Pembeli UI', is_complete=True)
        self.client.force_login(self.buyer)
        link = reverse('review_report:review_create', args=[self.deal.pk])
        self.assertContains(self.client.get(reverse('katalog:requests_page'), {'tab': 'keluar'}), link)
        self.assertContains(self.client.get(reverse('auth_ssoui:profile_history')), link)
        review = services.create_review(self.deal, self.buyer, rating=5, comment='Transaksi berjalan baik')
        detail = reverse('review_report:review_detail', args=[review.pk])
        self.assertContains(self.client.get(reverse('auth_ssoui:profile_history')), detail)

    def test_catalog_links_real_owner_rating_and_completed_request(self):
        url = reverse('katalog:item_detail', args=[self.item.pk])
        self.client.force_login(self.buyer)
        response = self.client.get(url)
        self.assertContains(response, reverse('review_report:report_item', args=[self.item.pk]))
        self.assertContains(response, reverse('review_report:report_user', args=[self.owner.pk]))
        self.assertContains(response, reverse('review_report:review_create', args=[self.deal.pk]))
        self.assertContains(response, 'Belum ada ulasan')
        review = services.create_review(self.deal, self.buyer, rating=4, comment='Transaksi berjalan baik')
        response = self.client.get(url)
        self.assertContains(response, reverse('review_report:review_detail', args=[review.pk]))
        self.assertContains(response, '1 ulasan')
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(url), reverse('review_report:review_create', args=[self.deal.pk]))

    def test_profile_links_and_real_transaction_history(self):
        Profile.objects.create(user=self.buyer, nama='Pembeli UI', is_complete=True)
        self.client.force_login(self.buyer)
        response = self.client.get(reverse('auth_ssoui:profile'))
        for name in ('my_reviews', 'my_reports', 'transactions'):
            self.assertContains(response, reverse('review_report:' + name))
        response = self.client.get(reverse('review_report:transactions'))
        self.assertContains(response, self.item.name)
        self.assertContains(response, reverse('review_report:review_create', args=[self.deal.pk]))
        self.item.soft_delete()
        self.assertContains(self.client.get(reverse('review_report:transactions')), self.item.name)
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(reverse('review_report:transactions')), self.item.name)

    def test_pending_request_does_not_offer_review_even_if_item_finished(self):
        ItemRequest.objects.filter(pk=self.deal.pk).update(status='PENDING')
        self.item.status = 'SELESAI'
        self.item.save()
        self.client.force_login(self.buyer)
        for url in (reverse('katalog:item_detail', args=[self.item.pk]), reverse('review_report:transactions')):
            self.assertNotContains(self.client.get(url), reverse('review_report:review_create', args=[self.deal.pk]))

    def test_htmx_delete_uses_destination_path_for_next_filter(self):
        review = services.create_review(self.deal, self.buyer, rating=4, comment='Transaksi berjalan baik')
        self.client.force_login(self.buyer)
        response = self.client.post(reverse('review_report:review_delete', args=[review.pk]), HTTP_HX_REQUEST='true')
        self.assertContains(response, 'hx-get="' + reverse('review_report:my_reviews') + '"')

    def test_model_validation_error_becomes_form_message(self):
        self.client.force_login(self.buyer)
        with patch('review_report.services.create_review', side_effect=ValidationError({'item_request': ['Transaksi sudah diulas.']})):
            response = self.client.post(reverse('review_report:review_create', args=[self.deal.pk]), {'rating': 4, 'comment': 'Transaksi berjalan baik'}, HTTP_HX_REQUEST='true')
        self.assertContains(response, 'Transaksi sudah diulas.', status_code=422)

    def test_my_reports_displays_item_target(self):
        services.create_report(self.buyer, category='SCAM', description='Barang tidak sesuai dengan deskripsi.', target_item=self.item)
        self.client.force_login(self.buyer)
        self.assertContains(self.client.get(reverse('review_report:my_reports')), self.item.name)
