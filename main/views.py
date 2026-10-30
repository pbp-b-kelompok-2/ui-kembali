from django.shortcuts import render
from django.db.models import Count, IntegerField, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce

from forum.models import Comment, ForumPost

def lobby(request):
    comment_counts = (
        Comment.objects.filter(post=OuterRef("pk"))
        .order_by()
        .values("post")
        .annotate(total=Count("pk"))
        .values("total")[:1]
    )

    like_through = ForumPost.liked_by.through
    post_fk_name = ForumPost.liked_by.field.m2m_field_name()
    like_counts = (
        like_through.objects.filter(**{f"{post_fk_name}__pk": OuterRef("pk")})
        .order_by()
        .values(post_fk_name)
        .annotate(total=Count("pk"))
        .values("total")[:1]
    )

    latest_forum_posts = (
        ForumPost.objects.select_related("author", "author__profile")
        .annotate(
            comment_count=Coalesce(Subquery(comment_counts), Value(0), output_field=IntegerField()),
            like_count=Coalesce(Subquery(like_counts), Value(0), output_field=IntegerField()),
        )
        .order_by("-created_at", "-pk")[:3]
    )
    return render(request, "lobby.html", {"latest_forum_posts": latest_forum_posts})
