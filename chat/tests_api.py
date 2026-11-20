from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from katalog.models import Item

from .models import Conversation, Message

User = get_user_model()


def make_item(owner, **overrides):
    data = {
        "name": "Kipas meja Cosmos",
        "description": "Kipas meja masih berfungsi dengan baik.",
        "category": Item.Category.ELEKTRONIK,
        "condition": Item.Condition.BAIK,
        "location_name": "Stasiun UI",
        "transaction_type": Item.TransactionType.JUAL,
        "price": 85_000,
        "contact": "081234567890",
    }
    data.update(overrides)
    return Item.objects.create(owner=owner, **data)


class ChatAPITest(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="pemilik", password="test-password")
        self.buyer = User.objects.create_user(username="peminat", password="test-password")
        self.other = User.objects.create_user(username="oranglain", password="test-password")
        self.item = make_item(self.owner)
        self.list_url = reverse("chat_api:conversation-list")

    def create_conversation(self):
        return Conversation.objects.create(item=self.item, buyer=self.buyer)

    def test_conversations_require_login(self):
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_lists_only_conversations_they_participate_in(self):
        conversation = self.create_conversation()
        Message.objects.create(
            conversation=conversation, sender=self.owner, body="Masih tersedia."
        )
        other_item = make_item(self.other, name="Meja belajar")
        Conversation.objects.create(item=other_item, buyer=self.owner)

        self.client.force_authenticate(user=self.buyer)
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([row["id"] for row in response.data], [str(conversation.pk)])
        self.assertEqual(response.data[0]["item_name"], self.item.name)
        self.assertEqual(response.data[0]["seller"], self.owner.username)
        self.assertEqual(response.data[0]["latest_message"], "Masih tersedia.")
        self.assertEqual(response.data[0]["unread_count"], 1)

    def test_create_starts_or_reuses_conversation(self):
        self.client.force_authenticate(user=self.buyer)

        created = self.client.post(
            self.list_url, {"item": str(self.item.pk)}, format="json"
        )
        reused = self.client.post(
            self.list_url, {"item": str(self.item.pk)}, format="json"
        )

        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(reused.status_code, status.HTTP_200_OK)
        self.assertEqual(created.data["id"], reused.data["id"])
        self.assertEqual(Conversation.objects.count(), 1)

    def test_user_cannot_start_conversation_with_themselves(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            self.list_url, {"item": str(self.item.pk)}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("item", response.data)
        self.assertEqual(Conversation.objects.count(), 0)

    def test_messages_are_limited_to_participants_and_marked_read(self):
        conversation = self.create_conversation()
        message = Message.objects.create(
            conversation=conversation, sender=self.buyer, body="Halo, masih ada?"
        )
        messages_url = reverse(
            "chat_api:conversation-messages", args=[conversation.pk]
        )

        self.client.force_authenticate(user=self.owner)
        response = self.client.get(messages_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["messages"][0]["body"], message.body)
        self.assertTrue(response.data["messages"][0]["is_read"])
        message.refresh_from_db()
        self.assertIsNotNone(message.read_at)

        self.client.force_authenticate(user=self.other)
        self.assertEqual(
            self.client.get(messages_url).status_code, status.HTTP_404_NOT_FOUND
        )

    def test_participant_can_send_validated_message(self):
        conversation = self.create_conversation()
        messages_url = reverse(
            "chat_api:conversation-messages", args=[conversation.pk]
        )
        self.client.force_authenticate(user=self.buyer)

        response = self.client.post(
            messages_url,
            {"body": "  <b>Halo!</b>  ", "sender_id": self.owner.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["message"]["body"], "Halo!")
        self.assertEqual(response.data["message"]["sender_id"], self.buyer.pk)
        self.assertEqual(Message.objects.get().sender, self.buyer)

    def test_invalid_messages_are_rejected(self):
        conversation = self.create_conversation()
        messages_url = reverse(
            "chat_api:conversation-messages", args=[conversation.pk]
        )
        self.client.force_authenticate(user=self.buyer)

        for body in ("  ", "x" * (Message.MAX_BODY_LENGTH + 1)):
            response = self.client.post(
                messages_url, {"body": body}, format="json"
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Message.objects.count(), 0)