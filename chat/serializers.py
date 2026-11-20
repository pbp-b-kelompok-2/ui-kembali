from django.utils.html import strip_tags
from rest_framework import serializers

from katalog.models import Item

from .models import Conversation, Message


class ConversationCreateSerializer(serializers.Serializer):
    item = serializers.PrimaryKeyRelatedField(queryset=Item.objects.all())

    def validate_item(self, item):
        request = self.context["request"]
        if item.owner_id == request.user.pk:
            raise serializers.ValidationError(
                "Kamu tidak dapat memulai percakapan dengan dirimu sendiri."
            )
        return item


class ConversationSerializer(serializers.ModelSerializer):
    item_id = serializers.UUIDField(read_only=True)
    item_name = serializers.CharField(source="item.name", read_only=True)
    buyer = serializers.CharField(source="buyer.username", read_only=True)
    seller = serializers.CharField(source="item.owner.username", read_only=True)
    latest_message = serializers.CharField(
        source="latest_message_body", read_only=True, allow_null=True
    )
    unread_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Conversation
        fields = [
            "id",
            "item_id",
            "item_name",
            "buyer",
            "seller",
            "latest_message",
            "unread_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class MessageCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ["body"]

    def validate_body(self, value):
        body = strip_tags(value).strip()
        if not body:
            raise serializers.ValidationError("Pesan tidak boleh kosong.")
        return body


class MessageSerializer(serializers.ModelSerializer):
    sender_id = serializers.IntegerField(read_only=True)
    sender_name = serializers.CharField(source="sender.username", read_only=True)
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "id",
            "sender_id",
            "sender_name",
            "body",
            "sent_at",
            "read_at",
            "is_read",
        ]
        read_only_fields = fields

    def get_is_read(self, message):
        return message.read_at is not None