from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth.models import AnonymousUser, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from .base import ModuleCase
from review_report import services
from review_report.models import Report


class ReportRuleTests(ModuleCase):
    def create(self, actor=None, **targets):
        return services.create_report(actor or self.buyer, category='SCAM', description='Barang tidak sesuai dengan deskripsi.', **(targets or {'target_item': self.item}))

    def test_report_does_not_require_transaction_and_server_sets_state(self):
        report = self.create(self.other, target_user=self.owner)
        self.assertEqual(report.reporter, self.other)
        self.assertEqual(report.status, 'PENDING')
        self.assertIsNone(report.reviewed_by)

    def test_invalid_targets_self_reporting_and_anonymous_rejected(self):
        for targets in ({}, {'target_user': self.owner, 'target_item': self.item}):
            with self.assertRaises(ValidationError):
                services.create_report(self.buyer, category='SCAM', description='Barang tidak sesuai dengan deskripsi.', **targets)
        for actor, targets in ((self.owner, {'target_user': self.owner}), (self.owner, {'target_item': self.item}), (AnonymousUser(), {'target_item': self.item})):
            with self.assertRaises(PermissionDenied):
                self.create(actor, **targets)

    def test_only_reporter_can_update_delete_and_only_while_pending(self):
        report = self.create()
        for actor in (self.owner, self.other):
            with self.assertRaises(PermissionDenied):
                services.update_report(report, actor, category='OTHER', description='Informasi masalah telah diperbarui.')
            with self.assertRaises(PermissionDenied):
                services.delete_report(report, actor)
        services.update_report(report, self.buyer, category='OTHER', description='Informasi masalah telah diperbarui.')
        report.refresh_from_db()
        self.assertEqual(report.category, 'OTHER')
        Report.objects.filter(pk=report.pk).update(status='IN_REVIEW')
        with self.assertRaises(ValidationError):
            services.update_report(report, self.buyer, category='SCAM', description='Informasi masalah telah diperbarui.')
        with self.assertRaises(ValidationError):
            services.delete_report(report, self.buyer)
        Report.objects.filter(pk=report.pk).update(status='PENDING')
        services.delete_report(report, self.buyer)
        self.assertFalse(Report.objects.exists())

    def test_duplicate_active_report_and_rate_limit(self):
        self.create()
        with self.assertRaises(ValidationError):
            self.create()
        for n in range(4):
            self.create(target_item=self.make_item(self.owner, name=f'Barang {n}'))
        with self.assertRaises(ValidationError):
            self.create(target_user=self.other)
        with patch('review_report.services.timezone.now', return_value=timezone.now()+timedelta(hours=2)):
            self.create(target_user=self.other)

    def test_deleted_item_cannot_be_new_report_target(self):
        self.item.soft_delete()
        with self.assertRaises(ValidationError):
            self.create()
