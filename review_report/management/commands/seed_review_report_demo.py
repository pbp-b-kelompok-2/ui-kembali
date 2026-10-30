"""Synthetic local demonstration data; never changes a non-demo account."""
import uuid
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from auth_ssoui.models import Profile
from katalog.models import Item, ItemRequest
from review_report.models import Review, Report
from review_report import services


class Command(BaseCommand):
    help = 'Create repeatable local review/report demo accounts and transactions (not production).'

    def add_arguments(self, parser):
        parser.add_argument('--password', required=True, help='Local demo password; not printed.')

    @transaction.atomic
    def handle(self, *args, **options):
        if getattr(settings, 'PRODUCTION', False):
            raise CommandError('Demo data is disabled in production.')
        group, _ = Group.objects.get_or_create(name='review-report-local-demo')
        users = {}
        for role in ('buyer', 'seller', 'other', 'moderator'):
            user, created = get_user_model().objects.get_or_create(username=f'rr_demo_{role}')
            if not created and not user.groups.filter(pk=group.pk).exists():
                raise CommandError(f'{user.username} already exists outside the demo; no accounts changed.')
            user.groups.add(group)
            # Local admin login gives demo sessions without adding an SSO bypass.
            # Buyer/seller/other have no model permissions and cannot moderate.
            user.is_staff = True
            user.set_password(options['password'])
            user.save()
            Profile.objects.get_or_create(user=user, defaults={'nama': f'Demo {role.title()}', 'nama_panggilan': role, 'faculty': 'Fasilkom', 'angkatan': '2025', 'is_complete': True})
            users[role] = user
        users['moderator'].user_permissions.add(Permission.objects.get(codename='moderate_report', content_type__app_label='review_report'))
        deals = []
        for n, (kind, req_status, item_status) in enumerate([
            ('ADOPSI', 'SELESAI', 'SELESAI'), ('JUAL', 'SELESAI', 'SELESAI'),
            ('ADOPSI', 'PENDING', 'TERSEDIA'), ('JUAL', 'PENDING', 'SELESAI'),
        ]):
            item, _ = Item.all_objects.get_or_create(pk=uuid.uuid5(uuid.NAMESPACE_URL, f'uikembali:review-report:demo:item:{n}'), defaults={
                'owner': users['seller'], 'name': ['Meja belajar demo', 'Lampu belajar demo', 'Buku kuliah demo', 'Kipas demo belum serah terima'][n],
                'description': 'Barang sintetis untuk demonstrasi modul Review dan Report.', 'category': 'PERABOT', 'condition': 'BAIK',
                'location_name': 'Kampus UI Depok', 'contact': 'Kontak sintetis demo', 'transaction_type': kind,
                'price': 25000 if kind == 'JUAL' else None, 'status': item_status,
            })
            deal, _ = ItemRequest.objects.get_or_create(pk=uuid.uuid5(uuid.NAMESPACE_URL, f'uikembali:review-report:demo:request:{n}'), defaults={'item': item, 'requester': users['buyer'], 'status': req_status})
            deals.append(deal)
        if not Review.objects.filter(item_request=deals[1]).exists():
            services.create_review(deals[1], users['buyer'], rating=5, comment='Barang sesuai deskripsi dan komunikasi sangat baik.')
        if not Report.objects.filter(reporter=users['buyer'], target_item=deals[2].item).exists():
            services.create_report(users['buyer'], target_item=deals[2].item, category='MISLEADING', description='Contoh laporan privat untuk demonstrasi pemeriksaan petugas.')
        self.stdout.write(self.style.SUCCESS('Demo ready. Accounts: rr_demo_buyer, rr_demo_seller, rr_demo_other, rr_demo_moderator.'))
        self.stdout.write('Sign in at /admin/login/, then open /review-report/transaksi/. Password is the supplied --password value.')
