from django import template
from django.utils import timezone

register = template.Library()


@register.filter
def rupiah(value):
    """55000 -> "Rp55.000"; no price means the item is free."""
    if value is None:
        return "Gratis"
    return f"Rp{value:,}".replace(",", ".")


@register.filter
def waktu_lalu(value):
    """Short Indonesian "time ago", like the cards in the design ("2 jam lalu")."""
    seconds = (timezone.now() - value).total_seconds()
    minutes, hours, days = seconds // 60, seconds // 3600, seconds // 86400
    if minutes < 1:
        return "baru saja"
    if hours < 1:
        return f"{minutes:.0f} menit lalu"
    if days < 1:
        return f"{hours:.0f} jam lalu"
    if days < 2:
        return "kemarin"
    if days < 30:
        return f"{days:.0f} hari lalu"
    if days < 365:
        return f"{days // 30:.0f} bulan lalu"
    return f"{days // 365:.0f} tahun lalu"


@register.filter
def jarak(km):
    """Distance on a card: "330 m" under 1 km, else "1,2 km"."""
    if km < 1:
        return f"{round(km * 100) * 10} m"
    return f"{km:.1f} km".replace(".", ",")
