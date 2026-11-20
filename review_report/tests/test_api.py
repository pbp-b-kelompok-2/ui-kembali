from django.contrib.auth.models import Permission
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from katalog.models import ItemRequest
from review_report.models import Report, Review

from .base import ModuleCase

GOOD_COMMENT = "Barang sesuai deskripsi, penjual ramah."
GOOD_REPORT = "Penjual meminta transfer di luar aplikasi sebelum bertemu."


class ApiCase(ModuleCase):
    def setUp(self):
        self.client = APIClient()

    def login(self, user):
        self.client.force_authenticate(user)


class ReviewApiTests(ApiCase):
    def create_url(self, deal=None):
        return reverse("review_report_api:review-create", args=[(deal or self.deal).pk])

    def test_create_review_as_requester(self):
        self.login(self.buyer)
        response = self.client.post(self.create_url(), {"rating": 5, "comment": GOOD_COMMENT}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["reviewer"], "buyer")
        self.assertEqual(response.data["reviewee"], "seller")
        self.assertTrue(response.data["is_author"])
        self.assertEqual(Review.objects.count(), 1)

    def test_create_requires_login(self):
        response = self.client.post(self.create_url(), {"rating": 5, "comment": GOOD_COMMENT}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_only_requester_can_review(self):
        for user in (self.owner, self.other):
            self.login(user)
            response = self.client.post(self.create_url(), {"rating": 5, "comment": GOOD_COMMENT}, format="json")
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Review.objects.count(), 0)

    def test_unfinished_transaction_is_conflict(self):
        pending = ItemRequest.objects.create(
            item=self.make_item(self.owner), requester=self.buyer, status="PENDING",
        )
        self.login(self.buyer)
        response = self.client.post(self.create_url(pending), {"rating": 5, "comment": GOOD_COMMENT}, format="json")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_duplicate_review_is_conflict(self):
        self.login(self.buyer)
        payload = {"rating": 4, "comment": GOOD_COMMENT}
        self.client.post(self.create_url(), payload, format="json")
        response = self.client.post(self.create_url(), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_validation_errors(self):
        self.login(self.buyer)
        for bad in ({"rating": 6, "comment": GOOD_COMMENT}, {"rating": 0, "comment": GOOD_COMMENT},
                    {"rating": 3, "comment": "pendek"}, {"rating": 3, "comment": "          "}, {}):
            response = self.client.post(self.create_url(), bad, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, bad)
        self.assertEqual(Review.objects.count(), 0)

    def make_review(self):
        return Review.objects.create(item_request=self.deal, rating=4, comment=GOOD_COMMENT)

    def test_detail_is_public(self):
        review = self.make_review()
        response = self.client.get(reverse("review_report_api:review-detail", args=[review.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_author"])

    def test_author_can_patch_and_delete_others_cannot(self):
        review = self.make_review()
        url = reverse("review_report_api:review-detail", args=[review.pk])

        self.login(self.other)
        self.assertEqual(self.client.patch(url, {"rating": 1}, format="json").status_code, 403)
        self.assertEqual(self.client.delete(url).status_code, 403)

        self.login(self.buyer)
        response = self.client.patch(url, {"rating": 2}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["rating"], 2)
        self.assertEqual(response.data["comment"], GOOD_COMMENT)
        self.assertEqual(self.client.put(url, {"rating": 3}, format="json").status_code, 400)
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertEqual(Review.objects.count(), 0)

    def test_anonymous_cannot_modify(self):
        review = self.make_review()
        url = reverse("review_report_api:review-detail", args=[review.pk])
        self.assertEqual(self.client.patch(url, {"rating": 1}, format="json").status_code, 403)
        self.assertEqual(self.client.delete(url).status_code, 403)

    def test_my_reviews_filter_and_scope(self):
        self.make_review()
        self.login(self.buyer)
        url = reverse("review_report_api:review-mine")
        self.assertEqual(self.client.get(url).data["count"], 1)
        self.assertEqual(self.client.get(url, {"rating": 5}).data["count"], 0)
        self.login(self.other)
        self.assertEqual(self.client.get(url).data["count"], 0)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_owner_reviews_public_with_summary(self):
        self.make_review()
        response = self.client.get(reverse("review_report_api:owner-reviews", args=[self.owner.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["summary"], {"average": 4.0, "count": 1})
        empty = self.client.get(reverse("review_report_api:owner-reviews", args=[self.other.pk]))
        self.assertEqual(empty.data["summary"], {"average": None, "count": 0})

    def test_transactions_expose_review_state(self):
        self.login(self.buyer)
        url = reverse("review_report_api:transaction-list")
        row = self.client.get(url).data["results"][0]
        self.assertTrue(row["can_review"])
        self.assertIsNone(row["review_id"])
        review = self.make_review()
        row = self.client.get(url).data["results"][0]
        self.assertFalse(row["can_review"])
        self.assertEqual(row["review_id"], review.pk)
        self.login(self.owner)
        self.assertFalse(self.client.get(url).data["results"][0]["can_review"])


class ReportApiTests(ApiCase):
    list_url = property(lambda self: reverse("review_report_api:report-list"))

    def post_report(self, **overrides):
        data = {"category": "SCAM", "description": GOOD_REPORT, "target_item": str(self.item.pk), **overrides}
        return self.client.post(self.list_url, data, format="json")

    def test_requires_login(self):
        self.assertEqual(self.client.get(self.list_url).status_code, 403)
        self.assertEqual(self.client.post(self.list_url, {}, format="json").status_code, 403)

    def test_create_item_and_user_report(self):
        self.login(self.buyer)
        response = self.post_report()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["target_type"], "item")
        self.assertEqual(response.data["status"], "PENDING")
        self.assertTrue(response.data["can_edit"])
        self.assertNotIn("internal_notes", response.data)
        response = self.client.post(
            self.list_url,
            {"category": "SPAM", "description": GOOD_REPORT, "target_user": self.owner.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["target_user"]["username"], "seller")

    def test_exactly_one_target(self):
        self.login(self.buyer)
        self.assertEqual(self.post_report(target_user=self.owner.pk).status_code, 400)
        data = {"category": "SCAM", "description": GOOD_REPORT}
        self.assertEqual(self.client.post(self.list_url, data, format="json").status_code, 400)

    def test_cannot_report_self_or_own_item(self):
        self.login(self.owner)
        self.assertEqual(self.post_report().status_code, 403)
        response = self.client.post(
            self.list_url,
            {"category": "SPAM", "description": GOOD_REPORT, "target_user": self.owner.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_invalid_input(self):
        self.login(self.buyer)
        self.assertEqual(self.post_report(category="NOPE").status_code, 400)
        self.assertEqual(self.post_report(description="terlalu pendek").status_code, 400)
        self.assertEqual(self.post_report(target_item="3f2504e0-4f89-41d3-9a0c-0305e82c3301").status_code, 400)

    def test_duplicate_active_report_is_conflict(self):
        self.login(self.buyer)
        self.assertEqual(self.post_report().status_code, 201)
        self.assertEqual(self.post_report().status_code, 409)

    def test_list_is_private_and_filterable(self):
        self.login(self.buyer)
        self.post_report()
        self.assertEqual(self.client.get(self.list_url).data["count"], 1)
        self.assertEqual(self.client.get(self.list_url, {"category": "SPAM"}).data["count"], 0)
        self.assertEqual(self.client.get(self.list_url, {"status": "PENDING"}).data["count"], 1)
        self.login(self.other)
        self.assertEqual(self.client.get(self.list_url).data["count"], 0)

    def test_detail_edit_delete_by_reporter_while_pending(self):
        self.login(self.buyer)
        report_id = self.post_report().data["id"]
        url = reverse("review_report_api:report-detail", args=[report_id])
        response = self.client.patch(url, {"category": "SPAM"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["category"], "SPAM")
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_not_editable_after_review_started(self):
        self.login(self.buyer)
        report_id = self.post_report().data["id"]
        Report.objects.filter(pk=report_id).update(status="IN_REVIEW")
        url = reverse("review_report_api:report-detail", args=[report_id])
        self.assertEqual(self.client.patch(url, {"category": "SPAM"}, format="json").status_code, 409)
        self.assertEqual(self.client.delete(url).status_code, 409)
        self.assertFalse(self.client.get(url).data["can_edit"])

    def test_other_users_cannot_see_or_touch_report(self):
        self.login(self.buyer)
        report_id = self.post_report().data["id"]
        url = reverse("review_report_api:report-detail", args=[report_id])
        for user in (self.owner, self.other):
            self.login(user)
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertEqual(self.client.patch(url, {"category": "SPAM"}, format="json").status_code, 404)
            self.assertEqual(self.client.delete(url).status_code, 404)

    def test_moderator_can_read_but_not_edit(self):
        self.login(self.buyer)
        report_id = self.post_report().data["id"]
        url = reverse("review_report_api:report-detail", args=[report_id])
        self.other.is_staff = True
        self.other.save()
        self.other.user_permissions.add(Permission.objects.get(codename="moderate_report"))
        self.login(self.other)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.patch(url, {"category": "SPAM"}, format="json").status_code, 404)


class MetaApiTests(ApiCase):
    def test_meta_is_public(self):
        response = self.client.get(reverse("review_report_api:meta"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["report_categories"]), len(Report.Category.choices))
