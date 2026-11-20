from rest_framework.permissions import BasePermission


class IsConversationParticipant(BasePermission):
    message = "Hanya peserta percakapan yang dapat mengaksesnya."

    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, conversation):
        return (
            conversation.buyer_id == request.user.pk
            or conversation.item.owner_id == request.user.pk
        )