from django.urls import path
from .views import *

app_name = "auth_ssoui"
urlpatterns = [
    path("login/", login_sso, name="login"),
    path("logout/", logout_sso, name="logout"),
]