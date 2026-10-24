from django.contrib import admin

from .models import Item, ItemRequest


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "category", "transaction_type", "price", "status", "is_deleted", "created_at")
    list_filter = ("status", "category", "transaction_type", "is_deleted")
    search_fields = ("name", "description", "location_name", "owner__username")

    def get_queryset(self, request):
        # Show soft-deleted items too, so admins can restore them.
        return Item.all_objects.select_related("owner")


@admin.register(ItemRequest)
class ItemRequestAdmin(admin.ModelAdmin):
    list_display = ("item", "requester", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("item__name", "requester__username")
