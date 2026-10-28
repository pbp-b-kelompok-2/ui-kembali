from unittest.mock import patch
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.urls import reverse
from review_report import services
from review_report.models import Report, Review
from .base import ModuleCase


class RegressionTests(ModuleCase):
    def setUp(self):
        self.client.force_login(self.buyer)

    def test_sensitive_html_not_saved_in_htmx_history_and_full_restore(self):
        report = services.create_report(self.buyer, target_user=self.owner, category='SPAM', description='Pesan mengganggu berulang kali diterima.')
        url = reverse('review_report:report_detail', args=[report.pk])
        response = self.client.get(url)
        self.assertContains(response, 'hx-history="false"')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertIn('Cookie', response['Vary'])
        self.assertContains(self.client.get(url, HTTP_HX_REQUEST='true', HTTP_HX_HISTORY_RESTORE_REQUEST='true'), '<html')

    def test_database_conflicts_leave_transaction_usable(self):
        with patch.object(Review, 'save', side_effect=IntegrityError('race')):
            with self.assertRaises(ValidationError):
                services.create_review(self.deal, self.buyer, rating=5, comment='Transaksi berjalan baik')
        with patch.object(Report, 'save', side_effect=IntegrityError('race')):
            with self.assertRaises(ValidationError):
                services.create_report(self.buyer, target_item=self.item, category='SCAM', description='Barang tidak sesuai dengan deskripsi.')
        self.assertFalse(Review.objects.exists())
        self.assertFalse(Report.objects.exists())

    def test_htmx_edit_form_errors_and_duplicate_get(self):
        review = services.create_review(self.deal, self.buyer, rating=5, comment='Transaksi berjalan baik')
        self.assertRedirects(self.client.get(reverse('review_report:review_create', args=[self.deal.pk])), reverse('review_report:review_detail', args=[review.pk]))
        edit = reverse('review_report:review_update', args=[review.pk])
        self.assertContains(self.client.get(edit), 'Transaksi berjalan baik')
        with patch('review_report.services.update_review', side_effect=ValidationError({'rating': ['Rating bermasalah.']})):
            self.assertContains(self.client.post(edit, {'rating': 3, 'comment': 'Perubahan komentar ulasan'}), 'Rating bermasalah.', status_code=422)

    def test_report_edit_htmx_error_self_targets_and_anonymous(self):
        url = reverse('review_report:report_user', args=[self.buyer.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse('review_report:report_item', args=[self.item.pk])).status_code, 403)
        self.client.force_login(self.buyer)
        report = services.create_report(self.buyer, target_item=self.item, category='SCAM', description='Barang tidak sesuai dengan deskripsi.')
        edit = reverse('review_report:report_update', args=[report.pk])
        self.assertContains(self.client.get(edit), report.description)
        with patch('review_report.services.update_report', side_effect=ValidationError('Perubahan ditolak.')):
            self.assertContains(self.client.post(edit, {'category': 'OTHER', 'description': 'Informasi masalah telah diperbarui.'}), 'Perubahan ditolak.', status_code=422)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('review_report:my_reports'), HTTP_HX_REQUEST='true').status_code, 204)

    def test_admin_workflow_rejects_skip_and_records_staff(self):
        self.other.is_staff = True
        self.other.save()
        self.other.user_permissions.add(Permission.objects.get(codename='moderate_report'))
        report = services.create_report(self.buyer, target_item=self.item, category='SCAM', description='Barang tidak sesuai dengan deskripsi.')
        url = reverse('admin:review_report_report_change', args=[report.pk])
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 200)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertContains(self.client.post(url, {'status': 'RESOLVED', 'public_result': 'Diperiksa.'}), 'Transisi status tidak diizinkan')
        for status, outcome in [('IN_REVIEW', ''), ('RESOLVED', 'Sudah ditindaklanjuti.')]:
            response = self.client.post(url, {'status': status, 'internal_notes': 'Rahasia petugas', 'public_result': outcome, 'reviewed_by': self.owner.pk, 'reporter': self.other.pk})
            self.assertEqual(response.status_code, 302)
        report.refresh_from_db()
        self.assertEqual(report.status, 'RESOLVED')
        self.assertEqual(report.reviewed_by, self.other)
        self.assertEqual(report.reporter, self.buyer)
        self.client.force_login(self.buyer)
        response = self.client.get(reverse('review_report:report_detail', args=[report.pk]))
        self.assertContains(response, 'Sudah ditindaklanjuti.')
        self.assertNotContains(response, 'Rahasia petugas')

    def test_second_owner_summary_and_report_status_pagination(self):
        from katalog.models import ItemRequest
        item = self.make_item(self.other)
        deal = ItemRequest.objects.create(item=item, requester=self.buyer, status='SELESAI')
        services.create_review(self.deal, self.buyer, rating=5, comment='Transaksi berjalan baik')
        services.create_review(deal, self.buyer, rating=1, comment='Pengalaman kurang baik')
        self.assertEqual(services.rating_summary(self.owner)['average'], 5)
        self.assertEqual(services.rating_summary(self.other)['average'], 1)
        for n in range(12):
            Report.objects.create(reporter=self.buyer, target_item=self.make_item(self.owner), category='OTHER', description='Keterangan masalah cukup panjang.', status='PENDING' if n < 11 else 'IN_REVIEW')
        url = reverse('review_report:my_reports')
        response = self.client.get(url, {'status': 'PENDING', 'page': 2}, HTTP_HX_REQUEST='true')
        self.assertEqual(len(response.context['page_obj']), 1)
        self.assertContains(response, 'status=PENDING')
        self.assertEqual(self.client.get(url, {'status': 'invalid'}).context['page_obj'].paginator.count, 12)
