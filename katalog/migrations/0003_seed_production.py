"""Empty on purpose: the seed moved to 0005_seed_production.

seed_katalog uses the real Item model, so here it would insert into columns
that only exist after 0004. The file stays because databases already recorded it.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("katalog", "0002_item_condition_choices"),
    ]

    operations = []
