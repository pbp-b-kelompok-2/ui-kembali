import json

from django import forms
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, OuterRef, Q, Subquery
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET, require_POST

from katalog.models import Item

from .models import Conversation, Message


class MessageForm(forms.Form):
    body = forms.CharField(max_length=Message.MAX_BODY_LENGTH, strip=True)


def _request_data(request):
    if request.content_type == "application/json":
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None
    return request.POST


def _conversation_for_user(request, conversation_id):
    return get_object_or_404(
        Conversation.objects.select_related("item", "item__owner", "buyer"),
        Q(buyer=request.user) | Q(item__owner=request.user),
        pk=conversation_id,
    )


def _message_data(message):
    return {
        "id": str(message.pk),
        "sender_id": message.sender_id,
        "sender_name": _display_name(message.sender),
        "body": message.body,
        "sent_at": message.sent_at.isoformat(),
        "is_read": message.read_at is not None,
    }


def _display_name(user):
    profile = getattr(user, "profile", None)
    return (profile.nama if profile else "") or user.get_full_name() or user.username


@login_required(login_url="/auth/login/")
@require_GET
def inbox(request):
    latest_body = Message.objects.filter(
        conversation_id=OuterRef("pk")
    ).order_by("-sent_at").values("body")[:1]
    conversations = (
        Conversation.objects.filter(Q(buyer=request.user) | Q(item__owner=request.user))
        .select_related(
            "item", "item__owner", "buyer", "buyer__profile", "item__owner__profile"
        )
        .annotate(
            latest_message_body=Subquery(latest_body),
            unread_count=Count(
                "messages",
                filter=Q(messages__read_at__isnull=True)
                & ~Q(messages__sender_id=request.user.pk),
            ),
        )
    )
    query = request.GET.get("q", "").strip()
    if query:
        conversations = conversations.filter(
            Q(item__name__icontains=query)
            | Q(buyer__username__icontains=query)
            | Q(item__owner__username__icontains=query)
        )
    return render(request, "chat/inbox.html", {"conversations": conversations})


@login_required(login_url="/auth/login/")
@require_POST
def start_conversation(request, item_id):
    item = get_object_or_404(Item.objects.select_related("owner"), pk=item_id)
    if item.owner_id == request.user.pk:
        return JsonResponse(
            {"error": "Kamu tidak dapat memulai percakapan dengan dirimu sendiri."},
            status=400,
        )

    data = _request_data(request)
    if data is None:
        return JsonResponse({"error": "Permintaan tidak valid."}, status=400)
    form = MessageForm({"body": data.get("body")}) if "body" in data else None
    if form is not None and not form.is_valid():
        return JsonResponse({"errors": form.errors.get_json_data()}, status=400)

    with transaction.atomic():
        conversation, created = Conversation.objects.get_or_create(
            item=item, buyer=request.user
        )
        if created and form is not None:
            Message.objects.create(
                conversation=conversation,
                sender=request.user,
                body=form.cleaned_data["body"],
            )
            conversation.save(update_fields=["updated_at"])

    return JsonResponse(
        {
            "conversation_id": str(conversation.pk),
            "url": reverse("chat:conversation", args=[conversation.pk]),
            "created": created,
        },
        status=201 if created else 200,
    )


@login_required(login_url="/auth/login/")
@require_GET
def conversation_detail(request, conversation_id):
    conversation = _conversation_for_user(request, conversation_id)
    Message.objects.filter(
        conversation=conversation, read_at__isnull=True
    ).exclude(sender=request.user).update(read_at=timezone.now())

    other_user = (
        conversation.item.owner
        if request.user == conversation.buyer
        else conversation.buyer
    )
    messages = conversation.messages.select_related("sender").all()
    return render(
        request,
        "chat/inbox.html",
        {
            "conversation": conversation,
            "other_user": other_user,
            "messages": messages,
        },
    )


@login_required(login_url="/auth/login/")
@require_GET
def conversation_messages(request, conversation_id):
    conversation = _conversation_for_user(request, conversation_id)
    messages = conversation.messages.select_related("sender")
    after = request.GET.get("after")
    if after:
        after_time = parse_datetime(after)
        if after_time is None or timezone.is_naive(after_time):
            return JsonResponse({"error": "Waktu pesan tidak valid."}, status=400)
        messages = messages.filter(sent_at__gte=after_time)
    Message.objects.filter(
        conversation=conversation, read_at__isnull=True
    ).exclude(sender=request.user).update(read_at=timezone.now())
    return JsonResponse(
        {"messages": [_message_data(message) for message in messages]}
    )


@login_required(login_url="/auth/login/")
@require_POST
def send_message(request, conversation_id):
    conversation = _conversation_for_user(request, conversation_id)
    data = _request_data(request)
    if data is None:
        return JsonResponse({"error": "Permintaan tidak valid."}, status=400)
    form = MessageForm(data)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors.get_json_data()}, status=400)

    message = Message.objects.create(
        conversation=conversation,
        sender=request.user,
        body=form.cleaned_data["body"],
    )
    conversation.save(update_fields=["updated_at"])
    return JsonResponse({"message": _message_data(message)}, status=201)
