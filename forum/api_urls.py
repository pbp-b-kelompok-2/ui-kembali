from rest_framework.routers import DefaultRouter

from .api_views import ForumCommentViewSet, ForumPostViewSet

router = DefaultRouter()
router.register("posts", ForumPostViewSet, basename="forum-post")
router.register("comments", ForumCommentViewSet, basename="forum-comment")

urlpatterns = router.urls
