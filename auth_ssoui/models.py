import os, uuid
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.db import models, transaction
from django.conf import settings
from io import BytesIO
from django.core.files.base import ContentFile
from PIL import Image, ImageOps


def pfp_upload_path(instance, filename):
    """Simpan pfp sebagai pfp/pfp_{username}.{ext} — overwrite otomatis."""
    return f"pfp/{uuid.uuid4().hex}.webp"

# Create your models here.

class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    # dari SSO
    nama = models.CharField(max_length=255, blank=True)
    peran = models.CharField(max_length=50, blank=True)
    faculty = models.CharField(max_length=255, blank=True)

    # diisi user
    pfp = models.ImageField(upload_to=pfp_upload_path, blank=True, null=True)
    no_hp = models.CharField(
        max_length=20,
        blank=True,
        validators=[RegexValidator(r"^(\+62|62|0)8[0-9]{8,12}$", "Format nomor HP tidak valid, contoh: 081234567890")],
    )
    angkatan = models.CharField(
        max_length=4,
        blank=True,
        validators=[RegexValidator(r"^20\d{2}$", "Isi dengan tahun 4 digit, contoh: 2025")],
    )
    nama_panggilan = models.CharField(max_length=50, blank=True)
    bio = models.CharField(max_length=160, blank=True)
    titik_favorit = models.CharField(max_length=255, blank=True)

    is_complete = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.nama} ({self.user.username})"

    def inisial(self):
        if (len(self.nama.split()) == 1):
            return self.nama.split()[0][0]
        return f"{self.nama.split()[0][0]}{self.nama.split()[-1][0]}"

    def save(self, *args, **kwargs):
        old_name = None
        if self.pk:
            old_name = (Profile.objects.filter(pk=self.pk)
                        .values_list("pfp", flat=True).first())

        f = self.pfp
        if f and not f._committed:                 # a new file was just uploaded
            img = ImageOps.exif_transpose(Image.open(f)).convert("RGB")
            img.thumbnail((512, 512))
            buf = BytesIO()
            img.save(buf, format="WEBP", quality=80)
            f.save("x.webp", ContentFile(buf.getvalue()), save=False)  # name comes from pfp_path

        super().save(*args, **kwargs)

        if old_name and old_name != self.pfp.name:  # delete the replaced file
            storage = self.pfp.storage
            transaction.on_commit(lambda: storage.delete(old_name))