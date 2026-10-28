import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from katalog.models import Item


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(
        Item, on_delete=models.CASCADE, related_name="chat_conversations"
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_conversations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["item", "buyer"], name="unique_chat_per_item_buyer"
            )
        ]

    @property
    def seller(self):
        return self.item.owner

    def clean(self):
        super().clean()
        if self.item_id and self.buyer_id and self.item.owner_id == self.buyer_id:
            raise ValidationError(
                {"buyer": "Pemilik barang tidak dapat menghubungi dirinya sendiri."}
            )

    def __str__(self):
        return f"{self.item}: {self.buyer}"


class Message(models.Model):
    MAX_BODY_LENGTH = 2000

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_messages"
    )
    body = models.CharField(max_length=MAX_BODY_LENGTH)
    sent_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["sent_at", "id"]
        indexes = [models.Index(fields=["conversation", "sent_at"])]

    def clean(self):
        super().clean()
        if self.conversation_id and self.sender_id:
            conversation = self.conversation
            if self.sender_id not in (
                conversation.buyer_id,
                conversation.item.owner_id,
            ):
                raise ValidationError(
                    {"sender": "Pengirim harus menjadi peserta percakapan."}
                )
        if self.body and not self.body.strip():
            raise ValidationError({"body": "Pesan tidak boleh kosong."})

    def __str__(self):
        return f"{self.sender}: {self.body[:40]}"
