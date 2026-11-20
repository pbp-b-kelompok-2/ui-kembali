"""JSON contract between Django and the mobile app for Review and Report."""
from django.contrib.auth import get_user_model
from rest_framework import serializers

from katalog.models import Item, ItemRequest
from katalog.serializers import TransactionSerializer

from .models import Report, Review


class ReviewSerializer(serializers.ModelSerializer):
    """Read shape of a review. Reviewer/reviewee come from the transaction."""

    transaction = serializers.UUIDField(source="item_request_id", read_only=True)
    item_id = serializers.UUIDField(source="item_request.item_id", read_only=True)
    item_name = serializers.CharField(source="item_request.item.name", read_only=True)
    transaction_type = serializers.CharField(
        source="item_request.item.transaction_type", read_only=True,
    )
    reviewer = serializers.CharField(source="item_request.requester.username", read_only=True)
    reviewee = serializers.CharField(source="item_request.item.owner.username", read_only=True)
    reviewee_id = serializers.IntegerField(source="item_request.item.owner_id", read_only=True)
    is_author = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = [
            "id", "transaction", "item_id", "item_name", "transaction_type",
            "reviewer", "reviewee", "reviewee_id", "is_author",
            "rating", "comment", "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_is_author(self, obj):
        request = self.context.get("request")
        return bool(
            request
            and request.user.is_authenticated
            and obj.item_request.requester_id == request.user.pk
        )


class ReviewInputSerializer(serializers.Serializer):
    """Create/update payload. Same limits as review_report.forms.ReviewForm."""

    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(min_length=10, max_length=1000)


class ReportSerializer(serializers.ModelSerializer):
    """Read shape of a report. internal_notes is never exposed to the reporter."""

    category_label = serializers.CharField(source="get_category_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    target_type = serializers.SerializerMethodField()
    target_item = serializers.SerializerMethodField()
    target_user = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = [
            "id", "category", "category_label", "description",
            "status", "status_label",
            "target_type", "target_item", "target_user",
            "public_result", "can_edit",
            "created_at", "updated_at", "reviewed_at", "resolved_at",
        ]
        read_only_fields = fields

    def get_target_type(self, obj):
        return "item" if obj.target_item_id else "user"

    def get_target_item(self, obj):
        if not obj.target_item_id:
            return None
        return {"id": obj.target_item_id, "name": obj.target_item.name}

    def get_target_user(self, obj):
        if not obj.target_user_id:
            return None
        return {"id": obj.target_user_id, "username": obj.target_user.username}

    def get_can_edit(self, obj):
        request = self.context.get("request")
        return bool(
            request
            and request.user.is_authenticated
            and obj.reporter_id == request.user.pk
            and obj.status == Report.Status.PENDING
        )


class ReportUpdateSerializer(serializers.Serializer):
    """Edit payload (reporter, PENDING only). Same limits as ReportForm."""

    category = serializers.ChoiceField(choices=Report.Category.choices)
    description = serializers.CharField(min_length=20, max_length=2000)


class ReportCreateSerializer(ReportUpdateSerializer):
    """Create payload: exactly one of target_item / target_user."""

    target_item = serializers.UUIDField(required=False)
    target_user = serializers.IntegerField(required=False)

    def validate(self, attrs):
        has_item, has_user = "target_item" in attrs, "target_user" in attrs
        if has_item == has_user:
            raise serializers.ValidationError("Pilih tepat satu target laporan: target_item atau target_user.")
        if has_item:
            try:
                attrs["target_item"] = Item.objects.get(pk=attrs["target_item"])
            except Item.DoesNotExist:
                raise serializers.ValidationError({"target_item": "Barang tidak ditemukan."})
        else:
            try:
                attrs["target_user"] = get_user_model().objects.get(pk=attrs["target_user"])
            except get_user_model().DoesNotExist:
                raise serializers.ValidationError({"target_user": "Pengguna tidak ditemukan."})
        return attrs


class ReviewTransactionSerializer(TransactionSerializer):
    """Riwayat transaksi plus what the mobile app needs to show "Beri ulasan"."""

    review_id = serializers.SerializerMethodField()
    can_review = serializers.SerializerMethodField()

    class Meta(TransactionSerializer.Meta):
        fields = TransactionSerializer.Meta.fields + ["review_id", "can_review"]
        read_only_fields = fields

    def get_review_id(self, obj):
        review = getattr(obj, "review", None)
        return review.pk if review else None

    def get_can_review(self, obj):
        return (
            obj.requester_id == self._user().pk
            and obj.status == ItemRequest.Status.SELESAI
            and getattr(obj, "review", None) is None
        )
