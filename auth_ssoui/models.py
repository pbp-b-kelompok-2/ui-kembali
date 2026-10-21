from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.db import models
from django.conf import settings

# Create your models here.

class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    # dari SSO
    nama = models.CharField(max_length=255, blank=True)
    peran = models.CharField(max_length=50, blank=True)
    faculty = models.CharField(max_length=255, blank=True)

    # diisi user
    pfp = models.ImageField(upload_to="pfp/", blank=True, null=True)
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