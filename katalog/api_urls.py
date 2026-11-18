from django.urls import path

from . import api_views

app_name = "api"

urlpatterns = [
    path("items/", api_views.item_list, name="item-list"),
    path("items/mine/", api_views.my_item_list, name="item-mine"),
    path("items/<uuid:item_id>/", api_views.item_detail, name="item-detail"),
    path("items/<uuid:item_id>/ajukan/", api_views.item_request_create, name="item-request"),
    path("transactions/", api_views.transaction_list, name="transaction-list"),
]
