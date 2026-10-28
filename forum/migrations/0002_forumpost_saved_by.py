from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("forum", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="forumpost",
            name="saved_by",
            field=models.ManyToManyField(
                blank=True,
                related_name="saved_forum_posts",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
