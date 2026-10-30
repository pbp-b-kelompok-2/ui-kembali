from django.urls import path
from .views import *

app_name = "auth_ssoui"
urlpatterns = [
    path("check/", get_login_cred, name=""),

    path("login/", login_sso, name="login"),
    path("logout/", logout_sso, name="logout"),

    path("profile/", profile_page, name="profile"), 
    path("profile/history/", profile_history, name="profile_history"),
    path("profile/fill/", lengkapi_profil, name="lengkapi_profil"),
    path("profile/edit/", edit_profil, name="edit_profil"),
    
]
