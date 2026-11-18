from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.html import strip_tags
from rest_framework import serializers

from .forms import validate_photo_upload
from .models import Item, ItemRequest

STRIPPED_FIELDS = ("name", "description", "location_name", "contact")
MIN_NAME_LENGTH = 3
MIN_DESCRIPTION_LENGTH = 10
PUBLIC_COORD_DIGITS = 3


class ItemSerializer(serializers.ModelSerializer):
    """Contract between Django and the mobile app for one Item."""

    owner = serializers.CharField(source="owner.username", read_only=True)
    is_owner = serializers.SerializerMethodField()
    category_label = serializers.CharField(source="get_category_display", read_only=True)
    condition_label = serializers.CharField(source="get_condition_display", read_only=True)
    photo = serializers.ImageField(write_only=True, required=False, allow_null=True)
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Item
        fields = [
            "id", "owner", "is_owner",
            "name", "description",
            "category", "category_label", "condition", "condition_label",
            "photo", "photo_url",
            "location_name", "latitude", "longitude",
            "transaction_type", "price", "contact",
            "status", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "latitude", "longitude", "status", "created_at", "updated_at",
        ]

    # --- output --------------------------------------------------------------

    def _viewer_is_logged_in(self):
        request = self.context.get("request")
        return request is not None and request.user.is_authenticated

    def get_is_owner(self, obj):
        request = self.context.get("request")
        return self._viewer_is_logged_in() and obj.owner_id == request.user.pk

    def get_photo_url(self, obj):
        if not obj.photo:
            return ""
        request = self.context.get("request")
        return request.build_absolute_uri(obj.photo.url) if request else obj.photo.url

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self._viewer_is_logged_in():
            # Same rule as the website: guests get no contact info and only an
            # approximate (~100 m) point on the map.
            data.pop("contact", None)
            for key in ("latitude", "longitude"):
                if data[key] is not None:
                    data[key] = round(data[key], PUBLIC_COORD_DIGITS)
        if hasattr(instance, "distance_km"):
            data["distance_km"] = round(instance.distance_km, 2)
        return data

    # --- input ---------------------------------------------------------------

    def validate_photo(self, value):
        return validate_photo_upload(value)

    def validate(self, attrs):
        for field in STRIPPED_FIELDS:
            if field in attrs:
                attrs[field] = strip_tags(attrs[field]).strip()
        if len(attrs.get("name", "x" * MIN_NAME_LENGTH)) < MIN_NAME_LENGTH:
            raise serializers.ValidationError(
                {"name": "Nama minimal 3 karakter (tanpa HTML)."}
            )
        if len(attrs.get("description", "x" * MIN_DESCRIPTION_LENGTH)) < MIN_DESCRIPTION_LENGTH:
            raise serializers.ValidationError(
                {"description": "Deskripsi minimal 10 karakter (tanpa HTML)."}
            )
        self._validate_price(attrs)
        return attrs

    def _validate_price(self, attrs):
        """Reuse Item.clean() so the API and the website share the price rules."""
        current = self.instance
        candidate = Item(
            transaction_type=attrs.get(
                "transaction_type",
                current.transaction_type if current else Item.TransactionType.ADOPSI,
            ),
            price=attrs.get("price", current.price if current else None),
        )
        try:
            candidate.clean()
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.message_dict)


class ItemRequestSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.name", read_only=True)
    requester = serializers.CharField(source="requester.username", read_only=True)

    class Meta:
        model = ItemRequest
        fields = [
            "id", "item", "item_name", "requester",
            "message", "status", "created_at",
        ]
        read_only_fields = ["id", "item", "status", "created_at"]

    def validate_message(self, value):
        return strip_tags(value).strip()
