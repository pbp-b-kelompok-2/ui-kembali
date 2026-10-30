from io import StringIO
from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import override_settings
from katalog.models import ItemRequest
from review_report.models import Review, Report
from .base import ModuleCase


class DemoCommandTests(ModuleCase):
    def test_seed_is_repeatable_and_provides_completed_and_ineligible_examples(self):
        for _ in range(2):
            call_command('seed_review_report_demo', password='Demo-password-123', stdout=StringIO())
        buyer = get_user_model().objects.get(username='rr_demo_buyer')
        moderator = get_user_model().objects.get(username='rr_demo_moderator')
        self.assertEqual(ItemRequest.objects.filter(requester=buyer, status='SELESAI').count(), 2)
        self.assertEqual(ItemRequest.objects.filter(requester=buyer).count(), 4)
        self.assertEqual(Review.objects.filter(item_request__requester=buyer).count(), 1)
        self.assertEqual(Report.objects.filter(reporter=buyer).count(), 1)
        self.assertTrue(moderator.has_perm('review_report.moderate_report'))
        self.assertFalse(moderator.is_superuser)
        self.assertTrue(buyer.check_password('Demo-password-123'))

    def test_never_overwrites_existing_non_demo_account(self):
        user = get_user_model().objects.create_user('rr_demo_buyer', password='original')
        with self.assertRaises(CommandError):
            call_command('seed_review_report_demo', password='Demo-password-123', stdout=StringIO())
        user.refresh_from_db()
        self.assertTrue(user.check_password('original'))

    @override_settings(PRODUCTION=True)
    def test_refuses_production(self):
        with self.assertRaises(CommandError):
            call_command('seed_review_report_demo', password='Demo-password-123', stdout=StringIO())
