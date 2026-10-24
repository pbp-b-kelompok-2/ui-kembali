# forms.py
from types import NoneType
import os
from django import forms
from django.utils.html import format_html
from django.db.models.fields.files import FieldFile
from .models import Profile
from django.core.files.uploadedfile import UploadedFile

class CompactImageInput(forms.FileInput):
    """File input kustom: tampilkan nama file yang sudah terupload menggantikan 'No file chosen'."""
    placeholder = "No file chosen"

    def render(self, name, value, attrs=None, renderer=None):
        attrs = dict(attrs or {})
        input_id = attrs.get("id", f"id_{name}")

        MAX_LEN = 24
        if isinstance(value, FieldFile) and value:
            current = os.path.basename(value.name)
            if len(current) > MAX_LEN:
                _, current_ext = os.path.splitext(current)
                keep = max(MAX_LEN - len(current_ext) - 3, 4)  # minimal 4 char tetap terlihat
                current = current[:keep] + "..." + current_ext
        else:
            current = self.placeholder

        attrs.update({
            "class": "pfp-file-hidden",
            "data-initial": current,
            "onchange": (
                "this.closest('.pfp-file-wrapper')"
                ".querySelector('.pfp-file-name').textContent = "
                "this.files.length ? this.files[0].name : this.dataset.initial;"
            ),
        })
        file_input = super().render(name, value, attrs, renderer)

        return format_html(
            '<div class="pfp-file-wrapper">{}'
            '<label for="{}" class="pfp-file-label">'
            '<span class="pfp-file-btn">Choose file</span>'
            '<span class="pfp-file-name">{}</span>'
            '</label></div>',
            file_input, input_id, current,
        )

SSO_FIELDS = ["nama", "faculty", "angkatan"]
USER_FIELDS = ["pfp", "nama_panggilan", "no_hp", "titik_favorit", "bio"]

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = SSO_FIELDS + USER_FIELDS
        labels = {
            "pfp": "Foto profil",
            "no_hp": "Nomor Whatsapp",
            "titik_favorit": "Titik temu favorit",
        }
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 2}),
            "pfp": CompactImageInput(attrs={"accept": "image/*"}),
            "titik_favorit": forms.TextInput(attrs={"placeholder": "Contoh: Perpustakaan UI, Danau Kenanga"}),
        }

    def __init__(self, *args, fields=None, **kwargs):
        super().__init__(*args, **kwargs)
        if fields is not None:
            for name in list(self.fields):
                if name not in fields:
                    del self.fields[name]
            self.order_fields(fields)
            for name in SSO_FIELDS:
                if name in fields:
                    self.fields[name].disabled = True

            # yang wajib diisi
            for name in ["nama_panggilan", "no_hp", "angkatan"]:
                if name in fields:
                    self.fields[name].required = True
        else:
            for name in SSO_FIELDS:
                self.fields[name].disabled = True
    
            # yang wajib diisi
            for name in ["nama_panggilan", "no_hp", "angkatan"]:
                self.fields[name].required = Tru    def clean_pfp(self):
        pfp = self.cleaned_data.get("pfp")
        # Hanya validasi jika ada file BARU yang diupload (bukan file lama yang tidak diubah)
        if isinstance(pfp, UploadedFile):
            if pfp.size > 2 * 1024 * 1024:
                raise forms.ValidationError("Ukuran foto maksimal 2 MB.")
            fmt = (getattr(pfp.image, "format", "") or "").upper()
            if fmt not in {"JPEG", "PNG", "WEBP"}:
                raise forms.ValidationError("Format harus JPG, PNG, atau WEBP.")
        return pfp