from django.shortcuts import render
from django.db.models import Count

from forum.models import ForumPost

def lobby(request):
    latest_forum_posts = (
        ForumPost.objects.select_related("author", "author__profile")
        .annotate(
            comment_count=Count("comments", distinct=True),
            like_count=Count("liked_by", distinct=True),
        )
        .order_by("-created_at", "-pk")[:3]
    )
    return render(request, "lobby.html", {"latest_forum_posts": latest_forum_posts})
