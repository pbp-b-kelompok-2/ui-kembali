import katalog.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("katalog", "0003_seed_production"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="item",
            name="photo_url",
        ),
        migrations.AddField(
            model_name="item",
            name="photo",
            field=models.ImageField(blank=True, upload_to=katalog.models.item_photo_path),
        ),
    ]
