from django import template

register = template.Library()


@register.filter
def display_name(user):
    """Full name if set, else username, else an em dash for no user at all."""
    if not user:
        return "—"
    return user.get_full_name() or user.username
