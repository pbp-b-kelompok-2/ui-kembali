from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.utils.html import strip_tags
from PIL import Image

from .models import Item

STRIPPED_FIELDS = ("name", "description", "location_name", "contact")
INPUT_CLASS = (
    "w-full rounded-lg border border-line bg-surface px-3 py-2.5 text-base "
    "outline-none focus:border-green focus:ring-2 focus:ring-green/20"
)
MAX_PHOTO_BYTES = 5 * 1024 * 1024
MAX_PHOTO_PIXELS = 25_000_000
PHOTO_FORMATS = {"JPEG", "PNG", "WEBP"}


class PhotoInput(forms.ClearableFileInput):
    initial_text = "Foto sekarang"
    input_text = "Ganti foto"
    clear_checkbox_label = "Hapus foto"


class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = [
            "name",
            "description",
            "category",
            "condition",
            "photo",
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
            "photo": "Foto barang",
            "location_name": "Lokasi temu",
            "transaction_type": "Jenis penawaran",
            "price": "Harga (Rp)",
            "contact": "Kontak (WA/Line)",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "transaction_type": forms.RadioSelect,
            "photo": PhotoInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            "name": "mis. Buku Kalkulus Purcell Edisi 9",
            "description": "Kondisi, kelengkapan, alasan dilepas…",
            "location_name": "mis. Perpustakaan UI, Kukusan",
            "contact": "mis. 0812xxxx atau ID Line",
            "price": "mis. 50000",
        }
        self.fields["photo"].error_messages["invalid_image"] = "Berkas harus berupa gambar."
        for name, field in self.fields.items():
            field.error_messages["required"] = "Wajib diisi."
            if name == "transaction_type":
                continue
            field.widget.attrs.setdefault("class", INPUT_CLASS)
            if name in placeholders:
                field.widget.attrs.setdefault("placeholder", placeholders[name])

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        # Only a new upload needs checking, not the photo already saved.
        if isinstance(photo, UploadedFile):
            if photo.size > MAX_PHOTO_BYTES:
                raise forms.ValidationError("Ukuran foto maksimal 5 MB.")
            if photo.image.format not in PHOTO_FORMATS:
                raise forms.ValidationError("Format harus JPG, PNG, atau WEBP.")
            # A small file can still decode into a huge image in memory.
            if photo.image.width * photo.image.height > MAX_PHOTO_PIXELS:
                raise forms.ValidationError("Resolusi foto terlalu besar.")
            # ImageField only checks the header; a cut-off file fails on decoding.
            try:
                with Image.open(photo) as image:
                    image.load()
            except (OSError, ValueError):
                raise forms.ValidationError("Berkas harus berupa gambar.")
            photo.seek(0)
        return photo

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
