from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from katalog.models import ItemRequest
from .base import ModuleCase
from review_report.models import Review
from review_report import services


class ReviewRuleTests(ModuleCase):
    def test_both_adoption_and_purchase_can_review(self):
        for kind in ('ADOPSI', 'JUAL'):
            item = self.make_item(self.owner, transaction_type=kind, price=10000 if kind == 'JUAL' else None)
            deal = ItemRequest.objects.create(item=item, requester=self.buyer, status='SELESAI')
            review = services.create_review(deal, self.buyer, rating=5, comment='Sangat baik dan ramah')
            self.assertEqual(review.item_request.requester, self.buyer)
            self.assertEqual(review.item_request.item.owner, self.owner)

    def test_anonymous_seller_and_third_party_cannot_review(self):
        for user in (AnonymousUser(), self.owner, self.other):
            with self.subTest(user=user), self.assertRaises(PermissionDenied):
                services.create_review(self.deal, user, rating=5, comment='Sangat baik dan ramah')
        self.assertFalse(Review.objects.exists())

    def test_item_finished_is_insufficient_and_all_unfinished_requests_fail(self):
        self.item.status = 'SELESAI'
        self.item.save()
        for status in ('PENDING', 'DITERIMA', 'DITOLAK', 'DIBATALKAN'):
            self.deal.status = status
            self.deal.save()
            with self.subTest(status=status), self.assertRaises(ValidationError):
                services.create_review(self.deal, self.buyer, rating=5, comment='Sangat baik dan ramah')

    def test_self_review_duplicate_and_invalid_input_fail(self):
        for rating, comment in ((0, 'Sangat baik dan ramah'), (6, 'Sangat baik dan ramah'), (3, 'x'), (3, 'x'*1001)):
            with self.assertRaises(ValidationError):
                services.create_review(self.deal, self.buyer, rating=rating, comment=comment)
        services.create_review(self.deal, self.buyer, rating=5, comment='Sangat baik dan ramah')
        with self.assertRaises(ValidationError):
            services.create_review(self.deal, self.buyer, rating=4, comment='Sangat baik dan ramah')
        self.deal.requester = self.owner
        self.deal.save()
        with self.assertRaises(PermissionDenied):
            services.create_review(self.deal, self.owner, rating=5, comment='Sangat baik dan ramah')

    def test_stale_request_status_is_reloaded(self):
        ItemRequest.objects.filter(pk=self.deal.pk).update(status='DITERIMA')
        with self.assertRaises(ValidationError):
            services.create_review(self.deal, self.buyer, rating=5, comment='Sangat baik dan ramah')
