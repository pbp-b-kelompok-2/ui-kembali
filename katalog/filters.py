from django import forms
from django.db.models import Count, Q
from django.db.models.functions import Coalesce

from .models import Item

SORT_ORDERS = {
    "newest": ("-created_at",),
    "oldest": ("created_at",),
    # Free items have no price, so treat them as the cheapest.
    "price_asc": ("price_or_zero", "-created_at"),
    "price_desc": ("-price_or_zero", "-created_at"),
    "name": ("name",),
}
SORT_CHOICES = [
    ("newest", "Terbaru"),
    ("oldest", "Terlama"),
    ("price_asc", "Harga terendah"),
    ("price_desc", "Harga tertinggi"),
    ("name", "Nama A–Z"),
]


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

    def values(self):
        """Cleaned values, skipping any field that failed validation."""
        self.is_valid()
        return {k: v for k, v in self.cleaned_data.items() if v not in (None, "", [])}

    def active_chips(self):
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
        return chips


def filter_items(params):
    form = CatalogFilterForm(params)
    values = form.values()
    # Finished items leave the catalog. select_related joins the owner in the
    # same query; pending_count is shown on every card.
    qs = (
        Item.objects.exclude(status=Item.Status.SELESAI)
        .select_related("owner")
        .annotate(
            pending_count=Count("requests", filter=Q(requests__status="PENDING"))
        )
    )

    if "q" in values:
        q = values["q"]
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
    if "category" in values:
        qs = qs.filter(category=values["category"])
    if "condition" in values:
        qs = qs.filter(condition__in=values["condition"])
    if "type" in values:
        qs = qs.filter(transaction_type__in=values["type"])
    if "location" in values:
        qs = qs.filter(location_name__icontains=values["location"])
    if "min_price" in values:
        # A free item counts as Rp0, so any min price above 0 excludes it.
        qs = qs.filter(price__gte=values["min_price"])
    if "max_price" in values:
        qs = qs.filter(Q(price__lte=values["max_price"]) | Q(price__isnull=True))

    sort = values.get("sort", "newest")
    if sort.startswith("price"):
        qs = qs.annotate(price_or_zero=Coalesce("price", 0))
    return form, qs.order_by(*SORT_ORDERS[sort])
