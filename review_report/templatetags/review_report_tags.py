from django import template
from katalog.models import ItemRequest
from review_report.services import rating_summary

register = template.Library()


@register.simple_tag
def owner_rating(owner):
    return rating_summary(owner)


@register.inclusion_tag('review_report/_item_actions.html', takes_context=True)
def item_review_actions(context, item):
    user = context['request'].user
    deals = ItemRequest.objects.none()
    if user.is_authenticated and user.pk != item.owner_id:
        deals = item.requests.filter(requester=user, status='SELESAI').select_related('review')
    return {'item': item, 'deals': deals, 'user': user}
