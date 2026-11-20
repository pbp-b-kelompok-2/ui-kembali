from django.urls import path

from . import api_views

app_name = "review_report_api"

urlpatterns = [
    path("meta/", api_views.meta, name="meta"),
    path("transactions/", api_views.transaction_list, name="transaction-list"),
    path("transactions/<uuid:pk>/review/", api_views.review_create, name="review-create"),
    path("reviews/mine/", api_views.my_review_list, name="review-mine"),
    path("reviews/<uuid:pk>/", api_views.review_detail, name="review-detail"),
    path("users/<int:pk>/reviews/", api_views.owner_review_list, name="owner-reviews"),
    path("reports/", api_views.report_list, name="report-list"),
    path("reports/<uuid:pk>/", api_views.report_detail, name="report-detail"),
]
