from importlib import import_module
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from katalog.models import Item

User = get_user_model()


class SeedKatalogTests(TestCase):
    def seed(self):
        call_command("seed_katalog", stdout=StringIO())

    def test_creates_at_least_50_items_and_5_users(self):
        self.seed()
        self.assertGreaterEqual(Item.objects.count(), 50)
        self.assertGreaterEqual(User.objects.filter(items__isnull=False).distinct().count(), 5)

    def test_items_are_valid_and_on_the_map(self):
        self.seed()
        for item in Item.objects.all():
            item.full_clean()
            self.assertIsNotNone(item.latitude, item.name)

    def test_running_twice_does_not_duplicate(self):
        self.seed()
        count = Item.objects.count()
        self.seed()
        self.assertEqual(Item.objects.count(), count)

    def test_has_free_and_paid_items_in_every_condition(self):
        self.seed()
        types = set(Item.objects.values_list("transaction_type", flat=True))
        conditions = set(Item.objects.values_list("condition", flat=True))
        self.assertEqual(types, set(Item.TransactionType.values))
        self.assertEqual(conditions, set(Item.Condition.values))


class SeedMigrationTests(TestCase):
    """Migration 0003 seeds PWS on deploy, since PWS has no shell to run seed_katalog."""

    def run_migration(self):
        migration = import_module("katalog.migrations.0003_seed_production")
        migration.seed_production(apps=None, schema_editor=None)

    @override_settings(PRODUCTION=True)
    def test_seeds_in_production(self):
        self.run_migration()
        self.assertGreaterEqual(Item.objects.count(), 50)

    @override_settings(PRODUCTION=False)
    def test_does_nothing_locally(self):
        self.run_migration()
        self.assertEqual(Item.objects.count(), 0)
