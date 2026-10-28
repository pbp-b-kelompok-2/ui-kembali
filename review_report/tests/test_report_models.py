from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from .base import ModuleCase
from review_report.models import Report


class ReportModelTests(ModuleCase):
    def report(self, **targets):
        return Report(reporter=self.buyer, category='SCAM', description='Dugaan penipuan barang', **targets)

    def test_exactly_one_target_required_by_validation_and_database(self):
        for targets in ({}, {'target_item': self.item, 'target_user': self.owner}):
            with self.assertRaises(ValidationError):
                self.report(**targets).full_clean()
            with self.assertRaises(IntegrityError), transaction.atomic():
                self.report(**targets).save()
        self.report(target_item=self.item).full_clean()
        self.report(target_user=self.owner).full_clean()

    def test_active_duplicates_constrained_but_closed_reports_allow_new_case(self):
        first = self.report(target_item=self.item)
        first.save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.report(target_item=self.item).save()
        first.status = 'RESOLVED'
        first.save()
        self.report(target_item=self.item).save()
        user_report = self.report(target_user=self.owner)
        user_report.save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.report(target_user=self.owner).save()

    def test_report_retained_on_soft_delete_and_target_protected(self):
        report = self.report(target_item=self.item)
        report.save()
        self.item.soft_delete()
        report.refresh_from_db()
        self.assertEqual(report.target_item.name, self.item.name)
        with self.assertRaises(ProtectedError):
            self.item.delete()
        with self.assertRaises(ProtectedError):
            self.buyer.delete()
