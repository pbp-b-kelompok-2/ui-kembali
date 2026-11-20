from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from .api_serializers import ForumCommentSerializer, ForumPostSerializer
from .models import Comment, ForumPost


class IsAuthorOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.method in permissions.SAFE_METHODS or obj.author_id == request.user.id


class ForumPostViewSet(viewsets.ModelViewSet):
    queryset = ForumPost.objects.select_related("author").all()
    serializer_class = ForumPostSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly)
    filter_backends = (SearchFilter, OrderingFilter)
    search_fields = ("title", "content")
    ordering_fields = ("created_at", "title")
    ordering = ("-created_at",)

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def like(self, request, pk=None):
        post = self.get_object()
        if post.liked_by.filter(pk=request.user.pk).exists():
            post.liked_by.remove(request.user)
            liked = False
        else:
            post.liked_by.add(request.user)
            liked = True
        return Response({"liked": liked, "like_count": post.liked_by.count()})

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def save(self, request, pk=None):
        post = self.get_object()
        if post.saved_by.filter(pk=request.user.pk).exists():
            post.saved_by.remove(request.user)
            saved = False
        else:
            post.saved_by.add(request.user)
            saved = True
        return Response({"saved": saved})


class ForumCommentViewSet(viewsets.ModelViewSet):
    serializer_class = ForumCommentSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly)
    http_method_names = ("get", "post", "patch", "delete", "head", "options")

    def get_queryset(self):
        queryset = Comment.objects.select_related("author", "post").all()
        post_id = self.request.query_params.get("post")
        if post_id:
            queryset = queryset.filter(post_id=post_id)
        return queryset

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.author_id != self.request.user.id:
            raise PermissionDenied("Hanya penulis komentar yang dapat mengubahnya.")
        serializer.save()
