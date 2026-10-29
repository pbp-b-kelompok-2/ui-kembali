from django.urls import path

from . import views

app_name = "forum"


urlpatterns = [
    path("", views.forum_list, name="forum_list"),
    path("post/<int:pk>/", views.post_detail, name="post_detail"),
    path("post/new/", views.post_create, name="post_create"),
    path("post/<int:pk>/edit/", views.post_update, name="post_update"),
    path("post/<int:post_pk>/attachment/<str:attachment_key>/delete/", views.attachment_delete, name="attachment_delete"),
    path("post/<int:pk>/delete/", views.post_delete, name="post_delete"),
    path("post/<int:pk>/comment/", views.comment_create, name="comment_create"),
    path("post/<int:pk>/like/", views.post_like, name="post_like"),
    path("post/<int:pk>/save/", views.post_save_toggle, name="post_save_toggle"),
    path("comment/<int:pk>/like/", views.comment_like, name="comment_like"),
]
