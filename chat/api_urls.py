from rest_framework.routers import DefaultRouter

from .api_views import ConversationViewSet

app_name = "chat_api"

router = DefaultRouter()
router.register("conversations", ConversationViewSet, basename="conversation")

urlpatterns = router.urls