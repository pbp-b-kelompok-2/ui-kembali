"""Seed the catalog on PWS during `migrate`.

PWS has no shell to run `python manage.py seed_katalog`, so this migration
runs it on deploy. Locally (PRODUCTION=False) it does nothing, so tests and
dev databases start empty. The seed command skips items that already exist.

seed_katalog uses the real Item model, so a later migration that adds a column
to Item must also move this seed after it.
"""

from django.conf import settings
from django.core.management import call_command
from django.db import migrations


def seed_production(apps, schema_editor):
    if settings.PRODUCTION:
        call_command("seed_katalog")


class Migration(migrations.Migration):

    dependencies = [
        ("katalog", "0004_replace_photo_url_with_photo"),
    ]

    operations = [
        migrations.RunPython(seed_production, migrations.RunPython.noop),
    ]
