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


@register.filter
def urgency_badge_class(is_done, days_to_match):
    """{{ is_done|urgency_badge_class:days_to_match }} - "success" once
    done, else a severity tier ("warning"/"orange"/"critical") based on how
    close the match is. Mirrors the Release Schedule delay-severity ladder
    so e.g. "Not Approved" 3 days out reads as more urgent than "Not
    Approved" a month out, instead of one flat warning color regardless of
    how much time is actually left."""
    if is_done:
        return "success"
    if days_to_match is None or days_to_match > 15:
        return "warning"
    if days_to_match >= 5:
        return "orange"
    return "critical"


@register.filter
def humanize_slug(value):
    """{{ value|humanize_slug }} - "ticket_design_delay" -> "Ticket Design
    Delay". Fallback formatting for a stored choice value that no longer
    matches any current TextChoices option (get_FOO_display() just echoes
    an unmatched value back unchanged, which otherwise shows up verbatim
    as a raw slug instead of readable text)."""
    if not value:
        return value
    return value.replace("_", " ").replace("-", " ").strip().title()


@register.filter
def abs_value(value):
    """{{ value|abs_value }} - Django templates have no builtin way to
    negate/abs a number (widthratio only produces a string, which fails
    blocktrans's "counter must be a number" check), so a negative
    days-until-match needs this to render as "N days ago"."""
    try:
        return abs(value)
    except TypeError:
        return value


@register.filter
def get_item(dictionary, key):
    """{{ some_dict|get_item:loop_var }} - Django's dot lookup only resolves
    a literal token as a dict key, not a variable's runtime value, so a
    dict keyed by something only known at render time (e.g. round number
    inside a {% for %}) needs this instead of {{ some_dict.loop_var }}."""
    if not dictionary:
        return None
    return dictionary.get(key)


@register.filter
def match_lifecycle_status(card):
    """{{ card|match_lifecycle_status }} - one of "tbc"/"past"/"live"/
    "happening"/"upcoming" for a build_dashboard_match_state dict, via the
    same classification the per-round stats card counts use (see
    operations.views.helpers.get_match_lifecycle_status), so an individual
    match's status badge always agrees with which bucket it's counted in."""
    from operations.views.helpers import get_match_lifecycle_status as _get_match_lifecycle_status

    return _get_match_lifecycle_status(card)
