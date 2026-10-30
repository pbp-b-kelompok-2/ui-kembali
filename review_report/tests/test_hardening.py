from django.core.exceptions import PermissionDenied, ValidationError
from review_report import services
from review_report.models import Review
from .base import ModuleCase


class InputAndRateLimitTests(ModuleCase):
    def test_fractional_and_boolean_ratings_are_rejected_without_coercion(self):
        for rating in (1.5, 3.0, True):
            with self.subTest(rating=rating), self.assertRaises(ValidationError):
                services.create_review(self.deal, self.buyer, rating=rating, comment='Pengalaman transaksi baik')
        self.assertFalse(Review.objects.exists())

    def test_inactive_accounts_cannot_submit(self):
        self.buyer.is_active = False
        self.buyer.save()
        with self.assertRaises(PermissionDenied):
            services.create_review(self.deal, self.buyer, rating=5, comment='Pengalaman transaksi baik')
        with self.assertRaises(PermissionDenied):
            services.create_report(self.buyer, target_user=self.owner, category='SPAM', description='Pesan berulang yang mengganggu.')

    def test_deleting_pending_reports_does_not_reset_hourly_submission_limit(self):
        for index in range(5):
            report = services.create_report(self.buyer, target_user=self.owner, category='SPAM', description='Pesan berulang yang mengganggu.')
            services.delete_report(report, self.buyer)
        with self.assertRaises(ValidationError):
            services.create_report(self.buyer, target_user=self.owner, category='SPAM', description='Pesan berulang yang mengganggu.')
