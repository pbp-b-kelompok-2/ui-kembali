from django import forms
from django.utils.html import strip_tags

from .models import Item

STRIPPED_FIELDS = ("name", "description", "location_name", "contact")


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
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

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
