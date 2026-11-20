from django.urls import path

from . import api_views

app_name = "auth_api"

urlpatterns = [
    path("profile/", api_views.profile_detail, name="profile-detail"),
    path("profile/edit/", api_views.profile_edit, name="profile-edit"),
    path("profile/fill/", api_views.profile_complete, name="profile-complete"),
]
