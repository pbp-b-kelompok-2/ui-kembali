import time

from django.core.management.base import BaseCommand
from django.db.models import Q

from katalog import geocoding
from katalog.models import Item


class Command(BaseCommand):
    help = "Retry geocoding for active items that were saved without coordinates."

    def add_arguments(self, parser):
        # Nominatim allows at most one request per second.
        parser.add_argument("--delay", type=float, default=1.0, help="seconds between items")

    def handle(self, *args, delay, **options):
        items = Item.objects.filter(Q(latitude__isnull=True) | Q(longitude__isnull=True))
        found, missing = 0, []
        for index, item in enumerate(items):
            if index and delay:
                time.sleep(delay)
            if geocoding.geocode_item(item):
                item.save(update_fields=["latitude", "longitude", "updated_at"])
                found += 1
            else:
                missing.append(item.location_name)
        self.stdout.write(f"{found} found, {len(missing)} not found")
        for name in missing:
            self.stdout.write(f"  - {name}")
