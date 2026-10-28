"""Turn a meeting place ("Kukusan", "Perpustakaan UI") into coordinates.

Order: cache → Nominatim (OpenStreetMap) → a small built-in table of campus
places. Whatever happens, saving an item never fails because of this module:
the worst case is an item without coordinates (no map, not in radius results).
"""

import math
import re
import sys
from typing import NamedTuple

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils.text import slugify

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Nominatim's usage policy asks for an identifying User-Agent.
USER_AGENT = "UIKembali/1.0 (PBP Fasilkom UI student project)"
TIMEOUT_SECONDS = 5
CACHE_SECONDS = 60 * 60 * 24 * 30  # places don't move
# Bias (not limit) results towards the UI Depok campus.
DEPOK_VIEWBOX = "106.78,-6.33,106.87,-6.40"
EARTH_RADIUS_KM = 6371.0


class Place(NamedTuple):
    label: str
    lat: float
    lng: float
    aliases: tuple[str, ...]


# Approximate centres of common meeting spots around UI Depok. Used when
# Nominatim is down or doesn't know the name, and for the "Dekat dengan" filter.
# First match wins, so more specific places come first.
PLACES = {
    "fasilkom": Place("Fasilkom UI", -6.36456, 106.82863, ("fasilkom", "ilmu komputer")),
    "perpustakaan": Place("Perpustakaan UI", -6.36533, 106.83168, ("perpustakaan ui", "perpus ui", "perpustakaan pusat")),
    "balairung": Place("Balairung UI", -6.36840, 106.83120, ("balairung",)),
    "stasiun_ui": Place("Stasiun UI", -6.36083, 106.83178, ("stasiun ui", "st ui")),
    "pondok_cina": Place("Pondok Cina", -6.36889, 106.83222, ("pondok cina", "pocin")),
    "asrama": Place("Asrama UI", -6.35070, 106.83057, ("asrama",)),
    "teknik": Place("Fakultas Teknik UI", -6.36190, 106.82390, ("fakultas teknik", "teknik ui", "ft ui")),
    "feb": Place("FEB UI", -6.35990, 106.82680, ("feb", "ekonomi dan bisnis")),
    "fmipa": Place("FMIPA UI", -6.36900, 106.82500, ("fmipa", "mipa")),
    "kukusan": Place("Kukusan", -6.36200, 106.82050, ("kukusan", "kutek")),
    "kober": Place("Kober / Barel", -6.35620, 106.83430, ("kober", "barel")),
    "margonda": Place("Margonda", -6.37300, 106.83260, ("margonda",)),
    "beji": Place("Beji", -6.37530, 106.81780, ("beji",)),
}


def _online():
    # Tests must never hit the real API (slow, and against Nominatim's policy),
    # so it's off under `manage.py test` unless a test turns it on explicitly.
    return getattr(settings, "KATALOG_GEOCODE_ONLINE", "test" not in sys.argv)


def lookup_place(query):
    """Built-in table: whole-word, case-insensitive alias match."""
    text = query.lower()
    for place in PLACES.values():
        if any(re.search(rf"\b{re.escape(alias)}\b", text) for alias in place.aliases):
            return place
    return None


def _ask_nominatim(query):
    try:
        response = requests.get(
            NOMINATIM_URL,
            params={
                "q": query,
                "format": "json",
                "limit": 1,
                "countrycodes": "id",
                "viewbox": DEPOK_VIEWBOX,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        hits = response.json()
        if not hits:
            return None
        return (float(hits[0]["lat"]), float(hits[0]["lon"]))
    except (requests.RequestException, ValueError, KeyError, TypeError, IndexError):
        # Timeout, HTTP error or an unexpected reply: let the table try.
        return None


def geocode(query):
    query = query.strip()
    if not query:
        return None
    key = f"geo:{slugify(query)}"
    cached = cache.get(key)
    if cached is not None:
        return tuple(cached)

    coords = None
    if _online():
        coords = _ask_nominatim(query)
    if coords is None:
        place = lookup_place(query)
        if place is not None:
            coords = (place.lat, place.lng)
    # Misses aren't cached, so `geocode_missing` can retry them later.
    if coords is not None:
        cache.set(key, coords, CACHE_SECONDS)
    return coords


def geocode_item(item):
    """Set (or clear) item.latitude/longitude from its location name. Doesn't save."""
    coords = geocode(item.location_name)
    item.latitude, item.longitude = coords or (None, None)
    return coords is not None


def haversine_km(lat1, lng1, lat2, lng2):
    """Great-circle distance: the length of the arc between two points on a sphere."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def bounding_box(lat, lng, km):
    """(min_lat, max_lat, min_lng, max_lng) of a square around the circle.

    A degree of latitude is always ~111 km; a degree of longitude shrinks with
    cos(latitude). The square is a cheap, index-friendly SQL prefilter; the
    exact circle check (haversine) runs afterwards on the few rows left.
    """
    km_per_degree = math.pi * EARTH_RADIUS_KM / 180
    dlat = km / km_per_degree
    dlng = km / (km_per_degree * math.cos(math.radians(lat)))
    return (lat - dlat, lat + dlat, lng - dlng, lng + dlng)
