from django.contrib.auth.models import Permission
from django.test import Client
from django.urls import reverse
from katalog.models import ItemRequest
from .base import ModuleCase
from review_report.models import Review, Report
from review_report import services


class ReviewHttpTests(ModuleCase):
    def url(self, name, *args):
        return reverse('review_report:' + name, args=args)

    def test_anonymous_login_and_htmx_session_expired(self):
        url = self.url('review_create', self.deal.pk)
        self.assertEqual(self.client.get(url).status_code, 302)
        response = self.client.post(url, HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 204)
        self.assertTrue(response['HX-Redirect'].startswith('/auth/login/'))

    def test_create_read_update_delete_authorization_and_methods(self):
        url = self.url('review_create', self.deal.pk)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {'rating': 5, 'comment': 'Pengalaman sangat baik'}).status_code, 403)
        self.client.force_login(self.buyer)
        self.assertContains(self.client.get(url), 'Ringkasan transaksi')
        response = self.client.post(url, {'rating': 5, 'comment': 'Pengalaman sangat baik', 'requester': self.other.pk, 'recipient': self.other.pk})
        self.assertEqual(response.status_code, 302)
        review = Review.objects.get()
        detail = self.url('review_detail', review.pk)
        self.assertContains(self.client.get(detail), 'Pengalaman sangat baik')
        edit, delete = self.url('review_update', review.pk), self.url('review_delete', review.pk)
        self.client.force_login(self.owner)
        for target in (edit, delete):
            self.assertEqual(self.client.post(target, {'rating': 1, 'comment': 'Tidak berhak mengubah'}).status_code, 403)
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get(delete).status_code, 405)
        self.assertEqual(self.client.put(edit).status_code, 405)
        self.client.post(edit, {'rating': 3, 'comment': 'Diperbarui dengan benar'})
        review.refresh_from_db()
        self.assertEqual(review.rating, 3)
        self.client.post(delete)
        self.assertFalse(Review.objects.exists())

    def test_invalid_htmx_form_and_duplicate_submission(self):
        self.client.force_login(self.buyer)
        url = self.url('review_create', self.deal.pk)
        response = self.client.post(url, {'rating': 6, 'comment': 'x'}, HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 422)
        self.assertContains(response, 'role="alert"', status_code=422)
        self.assertNotContains(response, '<html', status_code=422)
        data = {'rating': 5, 'comment': '<script>alert(1)</script>'}
        response = self.client.post(url, data, HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 200)
        self.assertIn('toast', response['HX-Trigger'])
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertContains(response, '&lt;script&gt;')
        self.assertEqual(self.client.post(url, data).status_code, 409)
        self.assertEqual(Review.objects.count(), 1)

    def test_lists_filters_summary_pagination_and_soft_deleted_history(self):
        self.client.force_login(self.buyer)
        for n in range(13):
            item = self.make_item(self.owner, transaction_type='JUAL' if n == 0 else 'ADOPSI', price=1000 if n == 0 else None)
            deal = ItemRequest.objects.create(item=item, requester=self.buyer, status='SELESAI')
            services.create_review(deal, self.buyer, rating=2 if n == 0 else 5, comment=f'Pengalaman baik nomor {n}')
        mine = self.url('my_reviews')
        response = self.client.get(mine)
        self.assertEqual(len(response.context['page_obj']), 10)
        self.assertEqual(len(self.client.get(mine, {'page': 2}).context['page_obj']), 3)
        response = self.client.get(mine, {'rating': 2, 'transaction_type': 'JUAL'}, HTTP_HX_REQUEST='true')
        self.assertEqual(response.context['page_obj'].paginator.count, 1)
        self.assertNotContains(response, '<html')
        owner_url = self.url('owner_reviews', self.owner.pk)
        response = self.client.get(owner_url, {'rating': 2})
        self.assertEqual(response.context['summary']['count'], 13)
        self.assertAlmostEqual(response.context['summary']['average'], 62/13)
        self.assertContains(self.client.get(self.url('owner_reviews', self.other.pk)), 'Belum ada ulasan')
        review = Review.objects.first()
        review.item_request.item.soft_delete()
        self.assertContains(self.client.get(self.url('review_detail', review.pk)), 'Pengalaman baik')
        self.assertEqual(self.client.get(mine, {'rating': 'invalid', 'page': 'bad'}).status_code, 200)

    def test_csrf_is_enforced(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.buyer)
        url = self.url('review_create', self.deal.pk)
        self.assertEqual(client.post(url, {'rating': 5, 'comment': 'Pengalaman sangat baik'}).status_code, 403)
        client.get(url)
        response = client.post(url, {'rating': 5, 'comment': 'Pengalaman sangat baik'}, HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 302)


class ReportHttpTests(ModuleCase):
    def url(self, name, *args):
        return reverse('review_report:' + name, args=args)

    def setUp(self):
        self.client.force_login(self.buyer)
        self.report = services.create_report(self.buyer, target_item=self.item, category='SCAM', description='Uraian privat yang cukup panjang.')

    def test_create_ignores_forged_server_fields_and_target(self):
        response = self.client.post(self.url('report_user', self.owner.pk), {'category': 'SPAM', 'description': 'Pesan spam berulang kali diterima.', 'status': 'RESOLVED', 'reporter': self.other.pk, 'reviewed_by': self.other.pk, 'target_item': str(self.item.pk)})
        self.assertEqual(response.status_code, 302)
        report = Report.objects.get(target_user=self.owner)
        self.assertEqual(report.status, 'PENDING')
        self.assertEqual(report.reporter, self.buyer)
        self.assertIsNone(report.target_item)
        self.assertIsNone(report.reviewed_by)
        self.assertEqual(self.client.get(self.url('report_item', self.item.pk)).status_code, 200)

    def test_privacy_includes_reported_party_and_unprivileged_staff(self):
        detail = self.url('report_detail', self.report.pk)
        Report.objects.filter(pk=self.report.pk).update(internal_notes='CATATAN RAHASIA')
        self.assertContains(self.client.get(detail), 'Uraian privat')
        self.assertNotContains(self.client.get(detail), 'CATATAN RAHASIA')
        for actor in (self.owner, self.other):
            self.client.force_login(actor)
            self.assertEqual(self.client.get(detail).status_code, 404)
            self.assertNotContains(self.client.get(self.url('my_reports')), 'Uraian privat')
        self.other.is_staff = True
        self.other.save()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.other.user_permissions.add(Permission.objects.get(codename='moderate_report'))
        self.assertEqual(self.client.get(detail).status_code, 200)

    def test_pending_edit_delete_lock_and_direct_url_ownership(self):
        edit, delete = self.url('report_update', self.report.pk), self.url('report_delete', self.report.pk)
        self.client.force_login(self.other)
        for url in (edit, delete):
            self.assertEqual(self.client.post(url).status_code, 404)
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get(delete).status_code, 405)
        self.assertEqual(self.client.post(edit, {'category': 'OTHER', 'description': 'Informasi masalah sudah diperbarui.'}).status_code, 302)
        self.report.refresh_from_db()
        self.assertEqual(self.report.category, 'OTHER')
        Report.objects.filter(pk=self.report.pk).update(status='IN_REVIEW')
        for url in (edit, delete):
            self.assertEqual(self.client.post(url).status_code, 409)
        Report.objects.filter(pk=self.report.pk).update(status='PENDING')
        self.assertEqual(self.client.post(delete, HTTP_HX_REQUEST='true').status_code, 200)
        self.assertFalse(Report.objects.exists())

    def test_status_filter_htmx_validation_and_csrf(self):
        Report.objects.filter(pk=self.report.pk).update(status='IN_REVIEW')
        response = self.client.get(self.url('my_reports'), {'status': 'PENDING'}, HTTP_HX_REQUEST='true')
        self.assertEqual(response.context['page_obj'].paginator.count, 0)
        self.assertNotContains(response, '<html')
        response = self.client.post(self.url('report_user', self.owner.pk), {'category': 'INVALID', 'description': 'x'}, HTTP_HX_REQUEST='true')
        self.assertContains(response, 'role="alert"', status_code=422)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.buyer)
        self.assertEqual(client.post(self.url('report_delete', self.report.pk)).status_code, 403)
