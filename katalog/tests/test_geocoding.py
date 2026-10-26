from io import StringIO
from unittest import mock

import requests
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from katalog import geocoding
from katalog.models import Item

from .test_models import make_item

User = get_user_model()
FASILKOM = geocoding.PLACES["fasilkom"]


def nominatim_reply(payload):
    response = mock.Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


@override_settings(KATALOG_GEOCODE_ONLINE=True)
@mock.patch("katalog.geocoding.requests.get")
class GeocodeOnlineTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_asks_nominatim_politely_and_parses_the_first_hit(self, get):
        get.return_value = nominatim_reply([{"lat": "-6.3700", "lon": "106.8300"}])
        self.assertEqual(geocoding.geocode("Perpustakaan UI"), (-6.37, 106.83))
        args, kwargs = get.call_args
        self.assertEqual(args[0], geocoding.NOMINATIM_URL)
        self.assertEqual(kwargs["params"]["q"], "Perpustakaan UI")
        self.assertEqual(kwargs["params"]["format"], "json")
        self.assertEqual(kwargs["params"]["limit"], 1)
        self.assertEqual(kwargs["params"]["countrycodes"], "id")
        self.assertIn("UIKembali", kwargs["headers"]["User-Agent"])
        self.assertEqual(kwargs["timeout"], 5)

    def test_result_is_cached(self, get):
        get.return_value = nominatim_reply([{"lat": "-6.37", "lon": "106.83"}])
        geocoding.geocode("Perpustakaan UI")
        # Same place, different spelling: one cache key, no second API call.
        self.assertEqual(geocoding.geocode("  perpustakaan ui "), (-6.37, 106.83))
        self.assertEqual(get.call_count, 1)

    def test_timeout_falls_back_to_the_place_table(self, get):
        get.side_effect = requests.Timeout
        self.assertEqual(geocoding.geocode("Gedung Fasilkom"), FASILKOM.coords)

    def test_empty_result_falls_back_to_the_place_table(self, get):
        get.return_value = nominatim_reply([])
        self.assertEqual(geocoding.geocode("Kukusan"), geocoding.PLACES["kukusan"].coords)

    def test_malformed_reply_falls_back(self, get):
        get.return_value = nominatim_reply([{"lat": "bukan angka"}])
        self.assertEqual(geocoding.geocode("Fasilkom"), FASILKOM.coords)

    def test_unknown_place_returns_none_and_is_not_cached(self, get):
        get.return_value = nominatim_reply([])
        self.assertIsNone(geocoding.geocode("Planet Mars"))
        geocoding.geocode("Planet Mars")
        # A miss isn't cached, so a later retry (geocode_missing) asks again.
        self.assertEqual(get.call_count, 2)

    def test_blank_query_never_calls_the_api(self, get):
        self.assertIsNone(geocoding.geocode("   "))
        get.assert_not_called()


@override_settings(KATALOG_GEOCODE_ONLINE=False)
class GeocodeOfflineTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @mock.patch("katalog.geocoding.requests.get")
    def test_offline_uses_only_the_table(self, get):
        self.assertEqual(geocoding.geocode("dekat STASIUN UI"), geocoding.PLACES["stasiun_ui"].coords)
        get.assert_not_called()

    def test_lookup_place_matches_aliases(self):
        self.assertEqual(geocoding.lookup_place("Kutek, gang Senggol"), geocoding.PLACES["kukusan"])
        self.assertEqual(geocoding.lookup_place("Fakultas Ilmu Komputer"), FASILKOM)
        self.assertIsNone(geocoding.lookup_place("Bandung"))


class DistanceTests(SimpleTestCase):
    def test_haversine_one_degree_on_the_equator(self):
        self.assertAlmostEqual(geocoding.haversine_km(0, 0, 0, 1), 111.19, places=1)

    def test_haversine_same_point_is_zero(self):
        self.assertEqual(geocoding.haversine_km(*FASILKOM.coords, *FASILKOM.coords), 0)

    def test_bounding_box_contains_the_circle(self):
        lat, lng = FASILKOM.coords
        min_lat, max_lat, min_lng, max_lng = geocoding.bounding_box(lat, lng, 2)
        # Points exactly 2 km north and east sit on the box edge, not outside it.
        self.assertAlmostEqual(geocoding.haversine_km(lat, lng, max_lat, lng), 2, places=2)
        self.assertAlmostEqual(geocoding.haversine_km(lat, lng, lat, max_lng), 2, places=2)
        self.assertLess(min_lat, lat)
        self.assertLess(min_lng, lng)


class GeocodeItemTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("pemilik", password="pw")

    @mock.patch("katalog.geocoding.geocode", return_value=(-6.1, 106.1))
    def test_sets_coordinates(self, geocode):
        item = make_item(self.owner)
        self.assertTrue(geocoding.geocode_item(item))
        geocode.assert_called_once_with("Kukusan")
        self.assertEqual((item.latitude, item.longitude), (-6.1, 106.1))

    @mock.patch("katalog.geocoding.geocode", return_value=None)
    def test_clears_stale_coordinates_when_not_found(self, geocode):
        item = make_item(self.owner, latitude=-6.1, longitude=106.1)
        self.assertFalse(geocoding.geocode_item(item))
        self.assertIsNone(item.latitude)
        self.assertIsNone(item.longitude)


class GeocodeMissingCommandTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("pemilik", password="pw")

    @mock.patch("katalog.geocoding.geocode")
    def test_fills_only_items_without_coordinates(self, geocode):
        geocode.side_effect = lambda q: (-6.2, 106.2) if q == "Kukusan" else None
        found = make_item(self.owner, location_name="Kukusan")
        missing = make_item(self.owner, location_name="Planet Mars")
        done = make_item(self.owner, latitude=-6.0, longitude=106.0)
        out = StringIO()
        call_command("geocode_missing", "--delay", "0", stdout=out)

        found.refresh_from_db()
        missing.refresh_from_db()
        done.refresh_from_db()
        self.assertEqual((found.latitude, found.longitude), (-6.2, 106.2))
        self.assertIsNone(missing.latitude)
        self.assertEqual(done.latitude, -6.0)
        self.assertEqual(geocode.call_count, 2)
        self.assertIn("1 found, 1 not found", out.getvalue())
        self.assertIn("Planet Mars", out.getvalue())

    @mock.patch("katalog.geocoding.geocode")
    def test_skips_deleted_items(self, geocode):
        item = make_item(self.owner)
        item.soft_delete()
        call_command("geocode_missing", "--delay", "0", stdout=StringIO())
        geocode.assert_not_called()
        self.assertEqual(Item.all_objects.get(pk=item.pk).latitude, None)
