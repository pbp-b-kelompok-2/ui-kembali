import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator
from django.db import models
from django.utils import timezone

MIN_PRICE = 1
MAX_PRICE = 100_000_000


class ActiveItemManager(models.Manager):
    """Default manager: hides soft-deleted items."""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class Item(models.Model):
    class Category(models.TextChoices):
        PERABOT = "PERABOT", "Perabot"
        ELEKTRONIK = "ELEKTRONIK", "Elektronik"
        BUKU = "BUKU", "Buku"
        PAKAIAN = "PAKAIAN", "Pakaian"
        ALAT_TULIS = "ALAT_TULIS", "Alat tulis"
        DAPUR = "DAPUR", "Dapur"
        LAINNYA = "LAINNYA", "Lainnya"

    class Condition(models.TextChoices):
        BARU = "BARU", "Baru"
        SEPERTI_BARU = "SEPERTI_BARU", "Seperti baru"
        BAIK = "BAIK", "Baik"
        LAYAK_PAKAI = "LAYAK_PAKAI", "Layak pakai"

    class TransactionType(models.TextChoices):
        ADOPSI = "ADOPSI", "Adopsi (gratis)"
        JUAL = "JUAL", "Jual"

    class Status(models.TextChoices):
        TERSEDIA = "TERSEDIA", "Tersedia"
        DIPESAN = "DIPESAN", "Dipesan"
        SELESAI = "SELESAI", "Selesai"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="items"
    )
    name = models.CharField(max_length=120, validators=[MinLengthValidator(3)])
    description = models.TextField(validators=[MinLengthValidator(10)])
    category = models.CharField(max_length=20, choices=Category.choices)
    condition = models.CharField(max_length=20, choices=Condition.choices)
    photo_url = models.URLField(blank=True)
    location_name = models.CharField(max_length=120)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    transaction_type = models.CharField(
        max_length=10, choices=TransactionType.choices, default=TransactionType.ADOPSI
    )
    price = models.PositiveIntegerField(null=True, blank=True)
    contact = models.CharField(max_length=100)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.TERSEDIA
    )
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ActiveItemManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["category"]),
            models.Index(fields=["transaction_type"]),
        ]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        super().clean()
        if self.transaction_type == self.TransactionType.JUAL:
            if self.price is None:
                raise ValidationError({"price": "Harga wajib diisi untuk barang dijual."})
            if not MIN_PRICE <= self.price <= MAX_PRICE:
                raise ValidationError(
                    {"price": f"Harga harus antara {MIN_PRICE} dan {MAX_PRICE:,}."}
                )
        elif self.price is not None:
            raise ValidationError({"price": "Barang adopsi tidak boleh punya harga."})

    def soft_delete(self) -> None:
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at", "updated_at"])

    def restore(self) -> None:
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=["is_deleted", "deleted_at", "updated_at"])


class ItemRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Menunggu"
        DITERIMA = "DITERIMA", "Diterima"
        DITOLAK = "DITOLAK", "Ditolak"
        DIBATALKAN = "DIBATALKAN", "Dibatalkan"
        SELESAI = "SELESAI", "Selesai"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="requests")
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="item_requests",
    )
    message = models.TextField(blank=True)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["item", "requester"],
                condition=models.Q(status="PENDING"),
                name="unique_pending_request_per_item",
            )
        ]

    def __str__(self) -> str:
        return f"{self.requester} → {self.item} ({self.status})"
