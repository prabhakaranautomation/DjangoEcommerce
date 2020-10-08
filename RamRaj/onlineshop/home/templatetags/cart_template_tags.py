from django import template
from ..models import Order

register = template.Library()


@register.filter
def cart_item_count(user):
    if user.is_authenticated:
        qs = Order.objects.filter(user=user, ordered=False)
        if qs.exists():
            total_item = 0
            for item in qs[0].items.all():
                total_item += item.quantity
            # return qs[0].items.count()
            return total_item
    return 0
