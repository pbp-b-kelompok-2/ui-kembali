from django import forms
from django.db.models import Count, Q, QuerySet
from django.db.models.functions import Coalesce

from . import geocoding
from .models import Item

DEFAULT_RADIUS_KM = 2
RADIUS_CHOICES = [(1, "1 km"), (2, "2 km"), (5, "5 km"), (10, "10 km")]

SORT_ORDERS = {
    "newest": ("-created_at",),
    "oldest": ("created_at",),
    # Free items have no price, so treat them as the cheapest.
    "price_asc": ("price_or_zero", "-created_at"),
    "price_desc": ("-price_or_zero", "-created_at"),
    "name": ("name",),
    # The real distance sort happens in Python (within_radius); newest first
    # breaks ties and is the fallback when there's no centre point.
    "distance": ("-created_at",),
}
SORT_CHOICES = [
    ("newest", "Terbaru"),
    ("oldest", "Terlama"),
    ("price_asc", "Harga terendah"),
    ("price_desc", "Harga tertinggi"),
    ("name", "Nama A–Z"),
    ("distance", "Terdekat"),
]
LIST_FIELDS = (
    "id",
    "name",
    "category",
    "condition",
    "photo_url",
    "location_name",
    "transaction_type",
    "price",
    "status",
    "created_at",
    "latitude",
    "longitude",
    "owner",
    "owner__username",
)


class CatalogFilterForm(forms.Form):
    """Reads the catalog's query string. Bad values are dropped, never a 400."""

    q = forms.CharField(required=False, max_length=100, label="Cari")
    category = forms.ChoiceField(
        required=False, choices=[("", "Semua kategori"), *Item.Category.choices]
    )
    condition = forms.MultipleChoiceField(
        required=False,
        choices=Item.Condition.choices,
        widget=forms.CheckboxSelectMultiple,
    )
    type = forms.MultipleChoiceField(
        required=False,
        choices=[
            (Item.TransactionType.ADOPSI, "Gratis"),
            (Item.TransactionType.JUAL, "Dijual"),
        ],
        widget=forms.CheckboxSelectMultiple,
    )
    location = forms.CharField(required=False, max_length=120, label="Lokasi temu")
    min_price = forms.IntegerField(required=False, min_value=0)
    max_price = forms.IntegerField(required=False, min_value=0)
    sort = forms.ChoiceField(required=False, choices=SORT_CHOICES)
    # Radius filter: the centre is a known place, or the browser's location.
    near = forms.ChoiceField(
        required=False,
        choices=[("", "Di mana saja"), *((k, p.label) for k, p in geocoding.PLACES.items())],
    )
    lat = forms.FloatField(required=False, min_value=-90, max_value=90)
    lng = forms.FloatField(required=False, min_value=-180, max_value=180)
    radius = forms.FloatField(required=False, min_value=0.1, max_value=50)

    def center(self) -> tuple[float, float, str] | None:
        """(lat, lng, label) of the radius filter's centre, if there is one."""
        values = self.values()
        if near := values.get("near"):
            place = geocoding.PLACES[near]
            return (place.lat, place.lng, place.label)
        if "lat" in values and "lng" in values:
            return (values["lat"], values["lng"], "lokasimu")
        return None

    def radius_km(self) -> float:
        return self.values().get("radius", DEFAULT_RADIUS_KM)

    def effective_sort(self) -> str:
        """Explicit ?sort= wins; otherwise nearest first when filtering by radius."""
        center = self.center()
        sort = self.values().get("sort") or ("distance" if center else "newest")
        return "newest" if sort == "distance" and not center else sort

    def values(self) -> dict:
        """Cleaned values, skipping any field that failed validation."""
        self.is_valid()
        return {k: v for k, v in self.cleaned_data.items() if v not in (None, "", [])}

    def active_chips(self) -> list[str]:
        """Labels for the "Filter aktif" row."""
        values = self.values()
        chips = []
        if "q" in values:
            chips.append(f"“{values['q']}”")
        if "category" in values:
            chips.append(Item.Category(values["category"]).label)
        chips += [Item.Condition(c).label for c in values.get("condition", [])]
        type_labels = dict(self.fields["type"].choices)
        chips += [type_labels[t] for t in values.get("type", [])]
        if "location" in values:
            chips.append(values["location"])
        if "min_price" in values:
            chips.append(f"≥ Rp{values['min_price']:,}".replace(",", "."))
        if "max_price" in values:
            chips.append(f"≤ Rp{values['max_price']:,}".replace(",", "."))
        if center := self.center():
            chips.append(f"≤ {self.radius_km():g} km dari {center[2]}")
        return chips


def catalog_queryset():
    """Base list query: one row per item, owner joined, pending requests counted."""
    return (
        Item.objects.exclude(status=Item.Status.SELESAI)
        .select_related("owner")
        .only(*LIST_FIELDS)
        .annotate(
            pending_count=Count(
                "requests", filter=Q(requests__status="PENDING"), distinct=True
            )
        )
    )


def within_radius(qs, lat, lng, km, by_distance) -> list[Item]:
    """Items within `km` of (lat, lng), each with a .distance_km attribute.

    Two steps: a bounding box in SQL throws away almost everything cheaply,
    then haversine in Python keeps only the true circle (the box's corners
    are ~1.4x further than its edges). Items without coordinates drop out.
    """
    min_lat, max_lat, min_lng, max_lng = geocoding.bounding_box(lat, lng, km)
    candidates = qs.filter(
        latitude__range=(min_lat, max_lat), longitude__range=(min_lng, max_lng)
    )
    items = []
    for item in candidates:
        item.distance_km = geocoding.haversine_km(lat, lng, item.latitude, item.longitude)
        if item.distance_km <= km:
            items.append(item)
    if by_distance:
        # sorted() is stable, so equal distances keep the SQL order (newest first).
        items.sort(key=lambda i: i.distance_km)
    return items


def filter_items(params) -> tuple[CatalogFilterForm, QuerySet | list[Item]]:
    form = CatalogFilterForm(params)
    values = form.values()
    qs = catalog_queryset()

    if q := values.get("q"):
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
    if category := values.get("category"):
        qs = qs.filter(category=category)
    if conditions := values.get("condition"):
        qs = qs.filter(condition__in=conditions)
    if types := values.get("type"):
        qs = qs.filter(transaction_type__in=types)
    if location := values.get("location"):
        qs = qs.filter(location_name__icontains=location)
    if "min_price" in values:
        # A free item counts as Rp0, so any min price above 0 excludes it.
        qs = qs.filter(price__gte=values["min_price"])
    if "max_price" in values:
        qs = qs.filter(Q(price__lte=values["max_price"]) | Q(price__isnull=True))

    sort = form.effective_sort()
    if sort.startswith("price"):
        qs = qs.annotate(price_or_zero=Coalesce("price", 0))
    qs = qs.order_by(*SORT_ORDERS[sort])
    if center := form.center():
        lat, lng, _ = center
        return form, within_radius(qs, lat, lng, form.radius_km(), sort == "distance")
    return form, qs
