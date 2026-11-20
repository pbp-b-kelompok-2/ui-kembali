from rest_framework import serializers

from .models import Comment, ForumPost


class ForumPostSerializer(serializers.ModelSerializer):
    author = serializers.CharField(source="author.username", read_only=True)
    like_count = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()

    class Meta:
        model = ForumPost
        fields = (
            "id", "title", "content", "category", "author", "created_at",
            "updated_at", "like_count", "comment_count", "is_liked", "is_saved",
        )
        read_only_fields = ("id", "author", "created_at", "updated_at")

    def get_like_count(self, obj):
        return obj.liked_by.count()

    def get_comment_count(self, obj):
        return obj.comments.count()

    def get_is_liked(self, obj):
        user = self.context["request"].user
        return user.is_authenticated and obj.liked_by.filter(pk=user.pk).exists()

    def get_is_saved(self, obj):
        user = self.context["request"].user
        return user.is_authenticated and obj.saved_by.filter(pk=user.pk).exists()


class ForumCommentSerializer(serializers.ModelSerializer):
    author = serializers.CharField(source="author.username", read_only=True)
    like_count = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ("id", "post", "parent", "content", "author", "created_at", "like_count")
        read_only_fields = ("id", "author", "created_at")

    def get_like_count(self, obj):
        return obj.liked_by.count()

    def validate_parent(self, parent):
        post = self.initial_data.get(
            "post", self.instance.post_id if self.instance is not None else None
        )
        if parent and str(parent.post_id) != str(post):
            raise serializers.ValidationError("Balasan harus berada di posting yang sama.")
        return parent
