from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import RequestFactory
from django.contrib.admin.sites import AdminSite
from .base import ModuleCase
from review_report import services
from review_report.models import Report


class ModerationTests(ModuleCase):
    def setUp(self):
        self.report = services.create_report(self.buyer, target_item=self.item, category='SCAM', description='Barang tidak sesuai dengan deskripsi.')
        self.other.is_staff = True
        self.other.save()

    def grant(self):
        self.other.user_permissions.add(Permission.objects.get(codename='moderate_report'))
        self.other = type(self.other).objects.get(pk=self.other.pk)

    def test_staff_without_explicit_permission_cannot_moderate(self):
        with self.assertRaises(PermissionDenied):
            services.moderate_report(self.report, self.other, 'IN_REVIEW')
        self.grant()
        self.other.is_staff = False
        with self.assertRaises(PermissionDenied):
            services.moderate_report(self.report, self.other, 'IN_REVIEW')

    def test_legal_transition_records_staff_time_and_separate_notes(self):
        self.grant()
        services.moderate_report(self.report, self.other, 'IN_REVIEW', internal_notes='Rahasia internal')
        self.report.refresh_from_db()
        self.assertEqual(self.report.reviewed_by, self.other)
        self.assertIsNotNone(self.report.reviewed_at)
        self.assertIsNone(self.report.resolved_at)
        services.moderate_report(self.report, self.other, 'RESOLVED', internal_notes='Rahasia internal', public_result='Sudah ditindaklanjuti.')
        self.report.refresh_from_db()
        self.assertEqual(self.report.public_result, 'Sudah ditindaklanjuti.')
        self.assertEqual(self.report.internal_notes, 'Rahasia internal')
        self.assertIsNotNone(self.report.resolved_at)

    def test_illegal_skip_reopen_and_missing_outcome_fail(self):
        self.grant()
        for status in ('RESOLVED', 'REJECTED', 'PENDING', 'UNKNOWN'):
            with self.assertRaises(ValidationError):
                services.moderate_report(self.report, self.other, status)
        services.moderate_report(self.report, self.other, 'IN_REVIEW')
        with self.assertRaises(ValidationError):
            services.moderate_report(self.report, self.other, 'REJECTED')
        services.moderate_report(self.report, self.other, 'REJECTED', public_result='Bukti tidak mencukupi.')
        with self.assertRaises(ValidationError):
            services.moderate_report(self.report, self.other, 'IN_REVIEW')

    def test_admin_access_requires_moderation_permission_and_prevents_add_delete(self):
        from review_report.admin import ReportAdmin
        admin = ReportAdmin(Report, AdminSite())
        request = RequestFactory().get('/admin/')
        request.user = self.other
        self.assertFalse(admin.has_view_permission(request, self.report))
        self.grant()
        request.user = self.other
        self.assertTrue(admin.has_view_permission(request, self.report))
        self.assertTrue(admin.has_change_permission(request, self.report))
        self.assertFalse(admin.has_add_permission(request))
        self.assertFalse(admin.has_delete_permission(request, self.report))
