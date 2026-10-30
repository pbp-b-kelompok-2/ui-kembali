import json

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from auth_ssoui.models import Profile
from katalog.models import Item

from .models import Conversation, Message

User = get_user_model()


def make_item(owner, **overrides):
    data = {
        "owner": owner,
        "name": "Kipas meja Cosmos",
        "description": "Kipas meja masih berfungsi dengan baik.",
        "category": Item.Category.ELEKTRONIK,
        "condition": Item.Condition.BAIK,
        "photo_url": "https://example.com/kipas.jpg",
        "location_name": "Stasiun UI",
        "transaction_type": Item.TransactionType.JUAL,
        "price": 85_000,
        "contact": "081234567890",
    }
    data.update(overrides)
    return Item.objects.create(**data)


class ChatTestCase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="pemilik")
        self.buyer = User.objects.create_user(username="peminat")
        self.other = User.objects.create_user(username="oranglain")
        for user, name in (
            (self.owner, "Raka Adiputra"),
            (self.buyer, "Nadia Ayuningtyas"),
            (self.other, "Dewi Sartika"),
        ):
            Profile.objects.create(user=user, nama=name, is_complete=True)
        self.item = make_item(self.owner)

    def json_post(self, url, payload):
        return self.client.post(
            url, data=json.dumps(payload), content_type="application/json"
        )


class ConversationModelTests(ChatTestCase):
    def test_conversation_links_item_and_buyer(self):
        conversation = Conversation.objects.create(
            item=self.item, buyer=self.buyer
        )

        self.assertEqual(conversation.seller, self.owner)
        self.assertEqual(list(self.buyer.chat_conversations.all()), [conversation])
        self.assertEqual(str(conversation), "Kipas meja Cosmos: peminat")

    def test_buyer_cannot_start_conversation_with_themselves(self):
        conversation = Conversation(item=self.item, buyer=self.owner)

        with self.assertRaises(ValidationError):
            conversation.full_clean()

    def test_only_one_conversation_per_item_and_buyer(self):
        Conversation.objects.create(item=self.item, buyer=self.buyer)

        with self.assertRaises(IntegrityError), transaction.atomic():
            Conversation.objects.create(item=self.item, buyer=self.buyer)


class MessageModelTests(ChatTestCase):
    def test_message_defaults_and_related_name(self):
        conversation = Conversation.objects.create(
            item=self.item, buyer=self.buyer
        )
        message = Message.objects.create(
            conversation=conversation, sender=self.buyer, body="Halo, masih ada?"
        )

        self.assertIsNone(message.read_at)
        self.assertEqual(list(conversation.messages.all()), [message])
        self.assertEqual(str(message), "peminat: Halo, masih ada?")

    def test_sender_must_be_a_conversation_participant(self):
        conversation = Conversation.objects.create(
            item=self.item, buyer=self.buyer
        )
        message = Message(
            conversation=conversation, sender=self.other, body="Halo"
        )

        with self.assertRaises(ValidationError):
            message.full_clean()


class ChatViewTests(ChatTestCase):
    def test_inbox_requires_login(self):
        response = self.client.get(reverse("chat:inbox"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("auth_ssoui:login"), response["Location"])

    def test_authenticated_user_can_open_empty_inbox(self):
        self.client.force_login(self.buyer)

        response = self.client.get(reverse("chat:inbox"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "chat/inbox.html")

    def test_buyer_can_start_a_conversation_over_ajax(self):
        self.client.force_login(self.buyer)

        response = self.json_post(
            reverse("chat:start", args=[self.item.pk]), {"body": "Halo!"}
        )

        self.assertEqual(response.status_code, 201)
        result = response.json()
        conversation = Conversation.objects.get()
        self.assertEqual(conversation.buyer, self.buyer)
        self.assertEqual(conversation.item, self.item)
        self.assertEqual(result["conversation_id"], str(conversation.pk))
        self.assertTrue(result["created"])
        self.assertEqual(conversation.messages.get().body, "Halo!")

    def test_starting_again_reuses_existing_conversation(self):
        self.client.force_login(self.buyer)
        url = reverse("chat:start", args=[self.item.pk])

        first = self.json_post(url, {})
        second = self.json_post(url, {})

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["conversation_id"], second.json()["conversation_id"])
        self.assertFalse(second.json()["created"])
        self.assertEqual(Conversation.objects.count(), 1)

    def test_user_cannot_start_chat_with_themselves(self):
        self.client.force_login(self.owner)

        response = self.json_post(
            reverse("chat:start", args=[self.item.pk]), {}
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Conversation.objects.count(), 0)

    def test_start_chat_for_deleted_item_returns_not_found(self):
        self.item.soft_delete()
        self.client.force_login(self.buyer)

        response = self.json_post(
            reverse("chat:start", args=[self.item.pk]), {}
        )

        self.assertEqual(response.status_code, 404)

    def test_invalid_json_cannot_start_conversation(self):
        self.client.force_login(self.buyer)

        response = self.client.post(
            reverse("chat:start", args=[self.item.pk]),
            data="{",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Conversation.objects.count(), 0)

    def test_participant_can_read_messages_and_their_unread_status_is_updated(self):
        conversation = Conversation.objects.create(
            item=self.item, buyer=self.buyer
        )
        message = Message.objects.create(
            conversation=conversation,
            sender=self.buyer,
            body="Apakah masih tersedia?",
        )
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("chat:messages", args=[conversation.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["messages"][0]["body"], message.body)
        self.assertTrue(response.json()["messages"][0]["is_read"])
        message.refresh_from_db()
        self.assertIsNotNone(message.read_at)

    def test_participant_can_open_conversation_with_item_summary(self):
        conversation = Conversation.objects.create(
            item=self.item, buyer=self.buyer
        )
        message = Message.objects.create(
            conversation=conversation, sender=self.buyer, body="Halo, masih ada?"
        )
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("chat:conversation", args=[conversation.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "chat/inbox.html")
        self.assertContains(response, self.item.name)
        self.assertContains(response, message.body)
        self.assertContains(response, self.buyer.profile.nama)
        self.assertContains(
            response,
            f'href="{reverse("chat:conversation", args=[conversation.pk])}"',
        )

    def test_read_status_is_only_rendered_for_own_messages(self):
        conversation = Conversation.objects.create(
            item=self.item, buyer=self.buyer
        )
        read_at = timezone.now()
        Message.objects.create(
            conversation=conversation,
            sender=self.buyer,
            body="Pesan dari pembeli",
            read_at=read_at,
        )
        Message.objects.create(
            conversation=conversation,
            sender=self.owner,
            body="Pesan dari pemilik",
            read_at=read_at,
        )
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("chat:conversation", args=[conversation.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "· Dibaca", count=1)
        self.assertContains(response, "data-message-own=\"true\"")
        self.assertContains(response, "data-message-own=\"false\"")
        self.assertContains(response, "data-[message-own=false]:self-start")
        self.assertContains(response, "data-[message-own=true]:bg-brand")

    def test_chat_page_loads_tailwind_utilities_without_chat_stylesheet(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse("chat:inbox"))

        self.assertContains(response, "@tailwind utilities")
        self.assertContains(response, "cdn.jsdelivr.net/npm/@tailwindcss/browser@4.1.13")
        self.assertContains(response, "grid-cols-[minmax(230px,280px)")
        self.assertNotContains(response, "chat/css/chat.css")

    def test_nonparticipant_cannot_read_conversation_or_messages(self):
        conversation = Conversation.objects.create(
            item=self.item, buyer=self.buyer
        )
        self.client.force_login(self.other)

        page = self.client.get(
            reverse("chat:conversation", args=[conversation.pk])
        )
        messages = self.client.get(
            reverse("chat:messages", args=[conversation.pk])
        )

        self.assertEqual(page.status_code, 404)
        self.assertEqual(messages.status_code, 404)

    def test_participant_can_send_a_message_over_ajax(self):
        conversation = Conversation.objects.create(
            item=self.item, buyer=self.buyer
        )
        self.client.force_login(self.owner)

        response = self.json_post(
            reverse("chat:send_message", args=[conversation.pk]),
            {"body": "  Besok pukul 16.30 ya?  "},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["message"]["body"], "Besok pukul 16.30 ya?")
        self.assertFalse(response.json()["message"]["is_read"])
        self.assertEqual(Message.objects.get().sender, self.owner)

    def test_empty_message_is_rejected(self):
        conversation = Conversation.objects.create(
            item=self.item, buyer=self.buyer
        )
        self.client.force_login(self.buyer)

        response = self.json_post(
            reverse("chat:send_message", args=[conversation.pk]), {"body": "  "}
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Message.objects.count(), 0)

    def test_message_over_maximum_length_is_rejected(self):
        conversation = Conversation.objects.create(
            item=self.item, buyer=self.buyer
        )
        self.client.force_login(self.buyer)

        response = self.json_post(
            reverse("chat:send_message", args=[conversation.pk]),
            {"body": "x" * (Message.MAX_BODY_LENGTH + 1)},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Message.objects.count(), 0)

    def test_invalid_incremental_message_timestamp_is_rejected(self):
        conversation = Conversation.objects.create(
            item=self.item, buyer=self.buyer
        )
        self.client.force_login(self.buyer)

        response = self.client.get(
            reverse("chat:messages", args=[conversation.pk]), {"after": "not-a-date"}
        )

        self.assertEqual(response.status_code, 400)

    def test_item_detail_offers_chat_to_logged_in_non_owner(self):
        self.client.force_login(self.buyer)

        response = self.client.get(
            reverse("katalog:item_detail", args=[self.item.pk])
        )

        self.assertContains(response, "Hubungi pemilik lewat chat")
        self.assertContains(response, reverse("chat:start", args=[self.item.pk]))

    def test_nonparticipant_cannot_send_message(self):
        conversation = Conversation.objects.create(
            item=self.item, buyer=self.buyer
        )
        self.client.force_login(self.other)

        response = self.json_post(
            reverse("chat:send_message", args=[conversation.pk]),
            {"body": "Saya ikut nimbrung"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(Message.objects.count(), 0)
