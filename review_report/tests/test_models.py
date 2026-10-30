from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from .base import ModuleCase
from review_report.models import Review


class ReviewModelTests(ModuleCase):
    def test_valid_ratings_and_comment_bounds(self):
        for rating in (1, 5):
            Review(item_request=self.deal, rating=rating, comment='Pengalaman yang baik').full_clean()
        for rating, comment in ((0, 'Pengalaman baik'), (6, 'Pengalaman baik'), (3, 'x'), (3, 'x' * 1001)):
            with self.subTest(rating=rating, length=len(comment)), self.assertRaises(ValidationError):
                Review(item_request=self.deal, rating=rating, comment=comment).full_clean()

    def test_database_rejects_invalid_rating_and_duplicate_transaction(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Review.objects.create(item_request=self.deal, rating=6, comment='Pengalaman baik')
        Review.objects.create(item_request=self.deal, rating=5, comment='Pengalaman baik')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Review.objects.create(item_request=self.deal, rating=4, comment='Pengalaman baik')

    def test_transaction_history_survives_soft_delete_and_blocks_hard_delete(self):
        review = Review.objects.create(item_request=self.deal, rating=5, comment='Pengalaman baik')
        self.item.soft_delete()
        self.assertEqual(Review.objects.get(pk=review.pk).item_request.item.name, self.item.name)
        with self.assertRaises(ProtectedError):
            self.item.delete()
