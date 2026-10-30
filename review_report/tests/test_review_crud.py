from django.core.exceptions import PermissionDenied
from .base import ModuleCase
from review_report import services
from review_report.models import Review


class ReviewCrudTests(ModuleCase):
    def test_only_author_may_update_and_delete(self):
        review = services.create_review(self.deal, self.buyer, rating=5, comment='Transaksi sangat baik')
        for actor in (self.owner, self.other):
            with self.assertRaises(PermissionDenied):
                services.update_review(review, actor, rating=1, comment='Tidak boleh mengubah')
            with self.assertRaises(PermissionDenied):
                services.delete_review(review, actor)
        services.update_review(review, self.buyer, rating=3, comment='Ulasan telah diperbarui')
        review.refresh_from_db()
        self.assertEqual(review.rating, 3)
        self.assertEqual(review.comment, 'Ulasan telah diperbarui')
        services.delete_review(review, self.buyer)
        self.assertFalse(Review.objects.exists())

    def test_summary_reflects_create_edit_delete_and_empty(self):
        self.assertEqual(services.rating_summary(self.owner), {'average': None, 'count': 0})
        review = services.create_review(self.deal, self.buyer, rating=5, comment='Transaksi sangat baik')
        self.assertEqual(services.rating_summary(self.owner), {'average': 5.0, 'count': 1})
        services.update_review(review, self.buyer, rating=3, comment='Ulasan telah diperbarui')
        self.assertEqual(services.rating_summary(self.owner), {'average': 3.0, 'count': 1})
        services.delete_review(review, self.buyer)
        self.assertEqual(services.rating_summary(self.owner), {'average': None, 'count': 0})
