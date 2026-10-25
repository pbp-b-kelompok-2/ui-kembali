from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from katalog.models import Item, ItemRequest

User = get_user_model()


def make_item(owner, **overrides):
    data = {
        "owner": owner,
        "name": "Meja belajar",
        "description": "Meja kayu, masih kokoh, cocok untuk kost.",
        "category": Item.Category.PERABOT,
        "condition": Item.Condition.BAIK,
        "location_name": "Kukusan",
        "transaction_type": Item.TransactionType.ADOPSI,
        "contact": "081234567890",
    }
    data.update(overrides)
    return Item.objects.create(**data)


class ItemModelTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("pemilik", password="pw")

    def test_defaults_and_str(self):
        item = make_item(self.owner)
        self.assertEqual(item.status, Item.Status.TERSEDIA)
        self.assertFalse(item.is_deleted)
        self.assertIsNone(item.deleted_at)
        self.assertIsNone(item.latitude)
        self.assertEqual(str(item), "Meja belajar")
        self.assertEqual(len(str(item.pk)), 36)  # UUID primary key

    def test_owner_related_name(self):
        item = make_item(self.owner)
        self.assertEqual(list(self.owner.items.all()), [item])

    def test_jual_requires_price(self):
        item = make_item(self.owner, transaction_type=Item.TransactionType.JUAL)
        with self.assertRaises(ValidationError) as ctx:
            item.full_clean()
        self.assertIn("price", ctx.exception.message_dict)

    def test_jual_price_must_be_within_range(self):
        item = make_item(
            self.owner, transaction_type=Item.TransactionType.JUAL, price=100_000_001
        )
        with self.assertRaises(ValidationError) as ctx:
            item.full_clean()
        self.assertIn("price", ctx.exception.message_dict)

    def test_jual_with_valid_price_is_ok(self):
        item = make_item(
            self.owner, transaction_type=Item.TransactionType.JUAL, price=50_000
        )
        item.full_clean()

    def test_adopsi_must_not_have_price(self):
        item = make_item(self.owner, price=10_000)
        with self.assertRaises(ValidationError) as ctx:
            item.full_clean()
        self.assertIn("price", ctx.exception.message_dict)

    def test_soft_delete_hides_from_default_manager(self):
        item = make_item(self.owner)
        item.soft_delete()
        item.refresh_from_db()
        self.assertTrue(item.is_deleted)
        self.assertIsNotNone(item.deleted_at)
        self.assertFalse(Item.objects.filter(pk=item.pk).exists())
        self.assertTrue(Item.all_objects.filter(pk=item.pk).exists())

    def test_restore_brings_item_back(self):
        item = make_item(self.owner)
        item.soft_delete()
        item.restore()
        item.refresh_from_db()
        self.assertFalse(item.is_deleted)
        self.assertIsNone(item.deleted_at)
        self.assertTrue(Item.objects.filter(pk=item.pk).exists())

    def test_condition_choices_match_design(self):
        self.assertEqual(
            Item.Condition.labels,
            ["Seperti baru", "Baik", "Cukup baik", "Layak pakai"],
        )

    def test_indexes_declared(self):
        index_fields = [tuple(index.fields) for index in Item._meta.indexes]
        self.assertIn(("status", "created_at"), index_fields)
        self.assertIn(("category",), index_fields)
        self.assertIn(("transaction_type",), index_fields)

    def test_default_ordering_is_newest_first(self):
        older = make_item(self.owner, name="Lama")
        newer = make_item(self.owner, name="Baru")
        Item.objects.filter(pk=older.pk).update(
            created_at=newer.created_at - timedelta(hours=1)
        )
        self.assertEqual(list(Item.objects.all()), [newer, older])


class ItemRequestModelTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("pemilik", password="pw")
        self.requester = User.objects.create_user("peminat", password="pw")
        self.item = make_item(self.owner)

    def test_defaults_and_related_name(self):
        req = ItemRequest.objects.create(
            item=self.item, requester=self.requester, message="Saya mau"
        )
        self.assertEqual(req.status, ItemRequest.Status.PENDING)
        self.assertEqual(list(self.item.requests.all()), [req])
        self.assertIn("peminat", str(req))

    def test_only_one_pending_request_per_user_and_item(self):
        ItemRequest.objects.create(item=self.item, requester=self.requester)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ItemRequest.objects.create(item=self.item, requester=self.requester)

    def test_new_request_allowed_after_old_one_closed(self):
        ItemRequest.objects.create(
            item=self.item,
            requester=self.requester,
            status=ItemRequest.Status.DIBATALKAN,
        )
        ItemRequest.objects.create(item=self.item, requester=self.requester)
        self.assertEqual(self.item.requests.count(), 2)
