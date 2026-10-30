"""Transaction-derived review identities and private, retained reports."""
import uuid
from django.conf import settings
from django.core.validators import MinLengthValidator, MaxLengthValidator, MinValueValidator, MaxValueValidator
from django.db import models


class Review(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item_request = models.OneToOneField('katalog.ItemRequest', on_delete=models.PROTECT, related_name='review')
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(validators=[MinLengthValidator(10), MaxLengthValidator(1000)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        constraints = [models.CheckConstraint(condition=models.Q(rating__gte=1, rating__lte=5), name='review_rating_1_to_5')]

    def __str__(self):
        return f'{self.rating}/5 · {self.item_request.item.name}'


class Report(models.Model):
    class Category(models.TextChoices):
        SCAM = 'SCAM', 'Penipuan'
        PROHIBITED = 'PROHIBITED', 'Barang terlarang'
        MISLEADING = 'MISLEADING', 'Deskripsi menyesatkan'
        HARASSMENT = 'HARASSMENT', 'Pelecehan'
        SPAM = 'SPAM', 'Spam'
        OTHER = 'OTHER', 'Lainnya'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Menunggu pemeriksaan'
        IN_REVIEW = 'IN_REVIEW', 'Sedang diperiksa'
        RESOLVED = 'RESOLVED', 'Selesai ditangani'
        REJECTED = 'REJECTED', 'Ditolak'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='reports')
    target_item = models.ForeignKey('katalog.Item', null=True, blank=True, on_delete=models.PROTECT, related_name='reports')
    target_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='reports_received')
    category = models.CharField(max_length=20, choices=Category.choices)
    description = models.TextField(validators=[MinLengthValidator(20), MaxLengthValidator(2000)])
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='reports_handled')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    internal_notes = models.TextField(blank=True)
    public_result = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        permissions = [('moderate_report', 'Can moderate private reports')]
        constraints = [
            models.CheckConstraint(condition=(models.Q(target_item__isnull=False, target_user__isnull=True) | models.Q(target_item__isnull=True, target_user__isnull=False)), name='report_exactly_one_target'),
            models.UniqueConstraint(fields=['reporter', 'target_item'], condition=models.Q(status__in=['PENDING', 'IN_REVIEW']), name='report_unique_active_item'),
            models.UniqueConstraint(fields=['reporter', 'target_user'], condition=models.Q(status__in=['PENDING', 'IN_REVIEW']), name='report_unique_active_user'),
            models.CheckConstraint(condition=models.Q(status__in=['PENDING', 'IN_REVIEW', 'RESOLVED', 'REJECTED']), name='report_valid_status'),
        ]

    def __str__(self):
        return f'{self.get_category_display()} · {self.get_status_display()}'
