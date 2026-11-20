from django.db import transaction
from django.db.models import Count, OuterRef, Q, Subquery
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Conversation, Message
from .permissions import IsConversationParticipant
from .serializers import (
    ConversationCreateSerializer,
    ConversationSerializer,
    MessageCreateSerializer,
    MessageSerializer,
)


class ConversationViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated, IsConversationParticipant]
    queryset = Conversation.objects.all()

    def get_queryset(self):
        user = self.request.user
        latest_message_body = (
            Message.objects.filter(conversation_id=OuterRef("pk"))
            .order_by("-sent_at", "-pk")
            .values("body")[:1]
        )
        return (
            Conversation.objects.filter(Q(buyer=user) | Q(item__owner=user))
            .select_related("item", "buyer", "item__owner")
            .annotate(
                unread_count=Count(
                    "messages",
                    filter=Q(messages__read_at__isnull=True)
                    & ~Q(messages__sender_id=user.pk),
                ),
                latest_message_body=Subquery(latest_message_body),
            )
        )

    def get_serializer_class(self):
        if self.action == "create":
            return ConversationCreateSerializer
        if self.action == "messages" and self.request.method == "POST":
            return MessageCreateSerializer
        if self.action == "messages":
            return MessageSerializer
        return ConversationSerializer

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = serializer.validated_data["item"]
        with transaction.atomic():
            conversation, created = Conversation.objects.get_or_create(
                item=item, buyer=request.user
            )
        output = ConversationSerializer(
            self.get_queryset().get(pk=conversation.pk),
            context=self.get_serializer_context(),
        )
        return Response(
            output.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get", "post"], url_path="messages")
    def messages(self, request, pk=None, **_kwargs):
        conversation = get_object_or_404(
            self.filter_queryset(self.get_queryset()), pk=pk
        )
        self.check_object_permissions(request, conversation)
        if request.method == "GET":
            messages = conversation.messages.select_related("sender")
            Message.objects.filter(
                conversation=conversation, read_at__isnull=True
            ).exclude(sender=request.user).update(read_at=timezone.now())
            serializer = MessageSerializer(
                messages, many=True, context=self.get_serializer_context()
            )
            return Response({"messages": serializer.data})

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = serializer.save(conversation=conversation, sender=request.user)
        conversation.save(update_fields=["updated_at"])
        return Response(
            {"message": MessageSerializer(message).data},
            status=status.HTTP_201_CREATED,
        )