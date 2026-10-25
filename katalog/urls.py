from django.urls import path

from . import views

app_name = "katalog"
urlpatterns = [
    path("", views.catalog_page, name="catalog"),
    path("list/", views.item_list_partial, name="item_list"),
    path("json/", views.items_json, name="items_json"),
    path("<uuid:pk>/", views.item_detail, name="item_detail"),
    path("<uuid:pk>/json/", views.item_detail_json, name="item_detail_json"),
    path("create/", views.item_create, name="item_create"),
    path("<uuid:pk>/edit/", views.item_update, name="item_update"),
    path("<uuid:pk>/delete/", views.item_soft_delete, name="item_soft_delete"),
    path("<uuid:pk>/restore/", views.item_restore, name="item_restore"),
]
