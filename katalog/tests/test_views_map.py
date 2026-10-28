from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from katalog.geocoding import PLACES
from katalog.models import Item
from katalog.templatetags.katalog_extras import jarak

from .test_models import make_item
from .test_views_crud import HX, VALID_POST, toast

User = get_user_model()
LAT, LNG = PLACES["fasilkom"].coords


class GeocodeOnSaveTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user("pemilik", password="pw")
        self.client.force_login(self.owner)

    @mock.patch("katalog.geocoding.geocode", return_value=(-6.36, 106.82))
    def test_create_stores_coordinates(self, geocode):
        response = self.client.post(reverse("katalog:item_create"), VALID_POST, **HX)
        self.assertEqual(response.status_code, 200)
        geocode.assert_called_once_with("Kukusan")
        item = Item.objects.get(name="Lampu belajar LED")
        self.assertEqual((item.latitude, item.longitude), (-6.36, 106.82))
        self.assertEqual(toast(response)["level"], "success")

    @mock.patch("katalog.geocoding.geocode", return_value=None)
    def test_create_saves_without_coordinates_and_warns(self, geocode):
        response = self.client.post(reverse("katalog:item_create"), VALID_POST, **HX)
        self.assertEqual(response.status_code, 200)
        item = Item.objects.get(name="Lampu belajar LED")
        self.assertIsNone(item.latitude)
        message = toast(response)
        self.assertEqual(message["level"], "info")
        self.assertIn("peta", message["msg"])

    @mock.patch("katalog.geocoding.geocode", return_value=(-6.30, 106.80))
    def test_update_geocodes_only_when_the_location_changes(self, geocode):
        item = make_item(self.owner, latitude=LAT, longitude=LNG)
        url = reverse("katalog:item_update", args=[item.pk])
        same = {**VALID_POST, "location_name": item.location_name}
        self.client.post(url, same, **HX)
        geocode.assert_not_called()

        self.client.post(url, {**VALID_POST, "location_name": "Margonda"}, **HX)
        geocode.assert_called_once_with("Margonda")
        item.refresh_from_db()
        self.assertEqual(item.latitude, -6.30)

    @mock.patch("katalog.geocoding.geocode", return_value=(-6.30, 106.80))
    def test_update_retries_an_item_that_has_no_coordinates_yet(self, geocode):
        item = make_item(self.owner)
        url = reverse("katalog:item_update", args=[item.pk])
        self.client.post(url, {**VALID_POST, "location_name": item.location_name}, **HX)
        geocode.assert_called_once()


class DetailMapTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("pemilik", password="pw")
        self.item = make_item(self.owner, latitude=-6.364612, longitude=106.828745)
        self.url = reverse("katalog:item_detail", args=[self.item.pk])

    def test_logged_in_users_get_the_exact_pin(self):
        self.client.force_login(User.objects.create_user("tamu", password="pw"))
        response = self.client.get(self.url)
        self.assertContains(response, 'id="item-map"')
        self.assertContains(response, 'data-lat="-6.364612"')
        self.assertContains(response, 'data-lng="106.828745"')
        self.assertContains(response, 'data-exact="true"')
        self.assertContains(response, "katalog/js/map.js")
        self.assertContains(response, "leaflet")

    def test_anonymous_users_only_get_an_area(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'data-lat="-6.365"')
        self.assertContains(response, 'data-lng="106.829"')
        self.assertContains(response, 'data-exact="false"')
        self.assertNotContains(response, "6.364612")

    def test_item_without_coordinates_has_no_map(self):
        Item.objects.filter(pk=self.item.pk).update(latitude=None, longitude=None)
        response = self.client.get(self.url)
        self.assertNotContains(response, 'id="item-map"')
        self.assertContains(response, "belum ada di peta")

    def test_detail_json_coordinates_follow_the_same_rule(self):
        url = reverse("katalog:item_detail_json", args=[self.item.pk])
        data = self.client.get(url).json()
        self.assertEqual((data["latitude"], data["longitude"]), (-6.365, 106.829))
        self.client.force_login(self.owner)
        data = self.client.get(url).json()
        self.assertEqual((data["latitude"], data["longitude"]), (-6.364612, 106.828745))


class RadiusFilterTests(TestCase):
    """Items placed north of Fasilkom: 0.1° of latitude ≈ 11.1 km."""

    @classmethod
    def setUpTestData(cls):
        owner = User.objects.create_user("pemilik", password="pw")
        cls.here = make_item(owner, name="Di Fasilkom", latitude=LAT, longitude=LNG)
        cls.near = make_item(owner, name="Dekat", latitude=LAT + 0.003, longitude=LNG)
        cls.mid = make_item(owner, name="Agak jauh", latitude=LAT + 0.015, longitude=LNG)
        cls.far = make_item(owner, name="Jakarta", latitude=LAT + 0.2, longitude=LNG)
        cls.unknown = make_item(owner, name="Tanpa koordinat")

    def names(self, params):
        response = self.client.get(reverse("katalog:catalog"), params)
        return [i.name for i in response.context["page_obj"]]

    def test_near_place_and_radius_sorts_by_distance(self):
        # "Di Fasilkom" is the oldest, so newest-first would list it last.
        self.assertEqual(self.names({"near": "fasilkom", "radius": "1"}), ["Di Fasilkom", "Dekat"])
        self.assertEqual(
            self.names({"near": "fasilkom", "radius": "5"}),
            ["Di Fasilkom", "Dekat", "Agak jauh"],
        )

    def test_coordinates_from_the_browser_work_too(self):
        params = {"lat": str(LAT + 0.015), "lng": str(LNG), "radius": "1"}
        self.assertEqual(self.names(params), ["Agak jauh"])

    def test_missing_or_bad_radius_uses_the_default(self):
        default = ["Di Fasilkom", "Dekat", "Agak jauh"]  # 2 km
        self.assertEqual(self.names({"near": "fasilkom"}), default)
        self.assertEqual(self.names({"near": "fasilkom", "radius": "999"}), default)
        self.assertEqual(self.names({"near": "fasilkom", "radius": "abc"}), default)

    def test_radius_alone_does_nothing(self):
        self.assertEqual(len(self.names({"radius": "1"})), 5)
        self.assertEqual(len(self.names({"near": "atlantis"})), 5)

    def test_explicit_sort_wins_over_distance(self):
        self.assertEqual(
            self.names({"near": "fasilkom", "radius": "5", "sort": "name"}),
            ["Agak jauh", "Dekat", "Di Fasilkom"],
        )

    def test_combines_with_other_filters(self):
        self.assertEqual(self.names({"near": "fasilkom", "radius": "5", "q": "dekat"}), ["Dekat"])

    def test_cards_show_distance_and_chip_names_the_place(self):
        response = self.client.get(reverse("katalog:catalog"), {"near": "fasilkom", "radius": "1"})
        items = list(response.context["page_obj"])
        self.assertEqual(items[0].distance_km, 0)
        self.assertAlmostEqual(items[1].distance_km, 0.33, places=2)
        self.assertContains(response, "330 m")
        self.assertIn("≤ 1 km dari Fasilkom UI", response.context["chips"])

    def test_query_count_stays_small(self):
        with CaptureQueriesContext(connection) as ctx:
            self.client.get(
                reverse("katalog:catalog"), {"near": "fasilkom", "radius": "50"}, HTTP_HX_REQUEST="true"
            )
        # count + page rows; the haversine step runs in Python, not per row.
        self.assertLessEqual(len(ctx.captured_queries), 3)

    def test_json_list_includes_distance(self):
        response = self.client.get(reverse("katalog:items_json"), {"near": "fasilkom", "radius": "1"})
        rows = response.json()["results"]
        self.assertEqual([r["name"] for r in rows], ["Di Fasilkom", "Dekat"])
        self.assertEqual(rows[1]["distance_km"], 0.33)


class JarakFilterTests(SimpleTestCase):
    def test_metres_below_one_km_then_one_decimal_km(self):
        self.assertEqual(jarak(0), "0 m")
        self.assertEqual(jarak(0.334), "330 m")
        self.assertEqual(jarak(1.25), "1,2 km")
        self.assertEqual(jarak(12), "12,0 km")
