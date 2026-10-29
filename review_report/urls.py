from django.urls import path
from . import views

app_name = 'review_report'
urlpatterns = [
    path('', views.home, name='home'),
    path('transaksi/', views.transactions, name='transactions'),
    path('ulasan/saya/', views.my_reviews, name='my_reviews'),
    path('pengguna/<int:pk>/ulasan/', views.owner_reviews, name='owner_reviews'),
    path('transaksi/<uuid:pk>/', views.review_create, name='review_create'),
    path('ulasan/<uuid:pk>/', views.review_detail, name='review_detail'),
    path('ulasan/<uuid:pk>/edit/', views.review_update, name='review_update'),
    path('ulasan/<uuid:pk>/hapus/', views.review_delete, name='review_delete'),
    path('laporkan/barang/<uuid:pk>/', views.report_item, name='report_item'),
    path('laporkan/pengguna/<int:pk>/', views.report_user, name='report_user'),
    path('laporan/saya/', views.my_reports, name='my_reports'),
    path('laporan/<uuid:pk>/', views.report_detail, name='report_detail'),
    path('laporan/<uuid:pk>/edit/', views.report_update, name='report_update'),
    path('laporan/<uuid:pk>/hapus/', views.report_delete, name='report_delete'),
]
