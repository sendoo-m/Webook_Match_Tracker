from django import template
from django.utils.translation import get_language

from operations.permissions import is_super_admin

register = template.Library()


@register.filter
def display_name(user):
    """Full name if set, else username, else an em dash for no user at all."""
    if not user:
        return "—"
    return user.get_full_name() or user.username


@register.filter
def localized_name(obj):
    """Picks name_ar or name_en based on the active UI language (falling
    back to whichever is non-empty) - replaces the ad-hoc mix of
    name_ar|default:name_en / raw .name_ar / raw .name_en used before the
    site had a language toggle, so bilingual data follows the same choice
    as the bilingual UI chrome."""
    if not obj:
        return ""
    if get_language() == "ar":
        return obj.name_ar or obj.name_en
    return obj.name_en or obj.name_ar


@register.filter
def is_admin_account(user):
    """True if this user is a top-tier admin account (superuser or "Super
    Admin" group) - used to hide the "Login as" action for accounts that
    can't legally be impersonated."""
    return is_super_admin(user)


CATEGORY_ICONS = {
    "Event Settings": "ti-settings",
    "Tickets": "ti-ticket",
    "Ticket Allocations": "ti-share-2",
    "Gates & Admins": "ti-door",
    "Manage Teams": "ti-users",
    "KVs": "ti-photo",
    "CMS Submission": "ti-upload",
    "Post Match": "ti-flag-2",
}


@register.filter
def category_icon(category_name):
    """Tabler icon class for a checklist category, so pending items are
    recognizable at a glance instead of by name alone."""
    return CATEGORY_ICONS.get(category_name, "ti-list-check")
