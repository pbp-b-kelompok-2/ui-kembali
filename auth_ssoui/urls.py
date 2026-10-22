from django.urls import path
from .views import *

app_name = "auth_ssoui"
urlpatterns = [
    path("check/", get_login_cred, name="check"),

    path("login/", login_sso, name="login"),
    path("logout/", logout_sso, name="logout"),

    path("profile-fill/", lengkapi_profil, name="lengkapi_profil"),
]