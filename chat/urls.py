from django.urls import path

from . import views

app_name = "chat"

urlpatterns = [
    path("", views.inbox, name="inbox"),
    path("start/<uuid:item_id>/", views.start_conversation, name="start"),
    path("<uuid:conversation_id>/", views.conversation_detail, name="conversation"),
    path(
        "<uuid:conversation_id>/messages/",
        views.conversation_messages,
        name="messages",
    ),
    path(
        "<uuid:conversation_id>/send/",
        views.send_message,
        name="send_message",
    ),
]
