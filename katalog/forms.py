from django import forms
from django.utils.html import strip_tags

from .models import Item

STRIPPED_FIELDS = ("name", "description", "location_name", "contact")
INPUT_CLASS = (
    "w-full rounded-lg border border-line bg-surface px-3 py-2.5 text-base "
    "outline-none focus:border-green focus:ring-2 focus:ring-green/20"
)


class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = [
            "name",
            "description",
            "category",
            "condition",
            "photo_url",
            "location_name",
            "transaction_type",
            "price",
            "contact",
        ]
        labels = {
            "name": "Nama barang",
            "description": "Deskripsi",
            "category": "Kategori",
            "condition": "Kondisi",
            "photo_url": "URL foto",
            "location_name": "Lokasi temu",
            "transaction_type": "Jenis penawaran",
            "price": "Harga (Rp)",
            "contact": "Kontak (WA/Line)",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "transaction_type": forms.RadioSelect,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            "name": "mis. Buku Kalkulus Purcell Edisi 9",
            "description": "Kondisi, kelengkapan, alasan dilepas…",
            "location_name": "mis. Perpustakaan UI, Kukusan",
            "contact": "mis. 0812xxxx atau ID Line",
            "photo_url": "https://…",
            "price": "mis. 50000",
        }
        for name, field in self.fields.items():
            if name == "transaction_type":
                continue
            field.widget.attrs.setdefault("class", INPUT_CLASS)
            if name in placeholders:
                field.widget.attrs.setdefault("placeholder", placeholders[name])

    def clean(self):
        cleaned = super().clean()
        for field in STRIPPED_FIELDS:
            if field in cleaned:
                cleaned[field] = strip_tags(cleaned[field]).strip()
        name = cleaned.get("name")
        if name is not None and len(name) < 3:
            self.add_error("name", "Nama minimal 3 karakter (tanpa HTML).")
        description = cleaned.get("description")
        if description is not None and len(description) < 10:
            self.add_error("description", "Deskripsi minimal 10 karakter (tanpa HTML).")
        return cleaned
