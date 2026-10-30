from django.contrib import admin
from django.urls import include, path, re_path
from django.conf import settings
from django.views.static import serve

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("main.urls")),
    path("auth/", include("auth_ssoui.urls")),
    path("katalog/", include("katalog.urls")),
    path("chat/", include("chat.urls")),
    path("forum/", include("forum.urls")),
    path("review-report/", include("review_report.urls")),
]

if settings.SERVE_MEDIA:
    media_prefix = settings.MEDIA_URL.lstrip("/")
    urlpatterns += [
        re_path(
            rf"^{media_prefix}(?P<path>.*)$",
            serve,
            {"document_root": settings.MEDIA_ROOT},
        )
    ]
