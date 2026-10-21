# forms.py
from django import forms
from .models import Profile

SSO_FIELDS = ["nama", "peran", "faculty"]
USER_FIELDS = ["pfp", "nama_panggilan", "no_hp", "angkatan", "bio", "titik_favorit"]

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = SSO_FIELDS + USER_FIELDS
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 1, "maxlength": 160}),
            "pfp": forms.ClearableFileInput(attrs={"accept": "image/*"}),
            "titik_favorit": forms.TextInput(attrs={"placeholder": "Contoh: Perpustakaan UI, Danau Kenanga"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in SSO_FIELDS:
            self.fields[name].disabled = True

        # yang wajib diisi
        for name in ["nama_panggilan", "no_hp", "angkatan"]:
            self.fields[name].required = True

    def clean_pfp(self):
        pfp = self.cleaned_data.get("pfp")
        if pfp and hasattr(pfp, "size") and pfp.size > 2 * 1024 * 1024:
            raise forms.ValidationError("Ukuran foto maksimal 2 MB.")
        return pfp