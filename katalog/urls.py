from django.urls import path

from . import views

app_name = "katalog"
urlpatterns = [
    path("", views.catalog_page, name="catalog"),
    path("list/", views.item_list_partial, name="item_list"),
    path("json/", views.items_json, name="items_json"),
    path("<uuid:pk>/", views.item_detail, name="item_detail"),
    path("<uuid:pk>/json/", views.item_detail_json, name="item_detail_json"),
]
