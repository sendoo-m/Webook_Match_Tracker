# events/permissions.py
#
# Category-scoped access for the events app, parallel to how
# operations/permissions.py scopes football matches by club+competition -
# except here a single EventCategoryAccess row (user, category, role) is the
# whole grant, since there's no separate "ownership" table to combine with.

from operations.permissions import can_manage_control_panel, is_super_admin

EVENTS_MANAGER_GROUP = "Events Manager"


def is_events_manager(user):
    """True for the global, unscoped "Events Manager" role - full authority
    across every category in the events app, without needing a per-category
    EventCategoryAccess grant. Distinct from football's Operations Manager:
    this role has no reach into the football side of the platform at all."""
    if not getattr(user, "is_authenticated", False):
        return False

    return user.groups.filter(name=EVENTS_MANAGER_GROUP).exists()


def get_user_category_ids(user, role=None):
    if not getattr(user, "is_authenticated", False):
        return []

    from .models import EventCategoryAccess

    qs = EventCategoryAccess.objects.filter(user=user)
    if role:
        qs = qs.filter(role=role)
    return list(qs.values_list("category_id", flat=True))


def can_manage_events_panel(user):
    """True for users allowed into the Events Panel: existing football
    managers keep their platform-wide authority, plus anyone granted the
    Admin role on at least one category (scoped to what they administer -
    enforced by the views/querysets, not by this flag)."""
    if not getattr(user, "is_authenticated", False):
        return False

    if user.is_superuser or can_manage_control_panel(user) or is_events_manager(user):
        return True

    from .models import EventCategoryAccess

    return EventCategoryAccess.objects.filter(user=user, role=EventCategoryAccess.Role.ADMIN).exists()


def can_view_events_hub(user):
    """True if this user has any reason to see the Events Hub link at all -
    either platform-wide manager access, or at least one category grant."""
    if not getattr(user, "is_authenticated", False):
        return False

    if user.is_superuser or can_manage_control_panel(user) or is_events_manager(user):
        return True

    return bool(get_user_category_ids(user))


def can_view_all_events(user):
    return getattr(user, "is_authenticated", False) and (
        user.is_superuser or can_manage_control_panel(user) or is_events_manager(user)
    )


def get_visible_events(user, queryset):
    if not getattr(user, "is_authenticated", False):
        return queryset.none()

    if can_view_all_events(user):
        return queryset

    category_ids = get_user_category_ids(user)
    if not category_ids:
        return queryset.none()

    return queryset.filter(category_id__in=category_ids)


def user_can_manage_event(user, event):
    """True if this user can perform event-level actions (checklist updates,
    send-to-CMS, CMS status changes) on THIS specific event.

    - Super Admin (or Django superuser): always.
    - Everyone else: any EventCategoryAccess grant (Coordinator or Admin) on
      the event's category - unlike football, there's no "manager reviews
      but doesn't execute" split requested for this app."""
    if not getattr(user, "is_authenticated", False):
        return False

    if user.is_superuser or is_super_admin(user) or is_events_manager(user):
        return True

    from .models import EventCategoryAccess

    return EventCategoryAccess.objects.filter(user=user, category_id=event.category_id).exists()


def require_event_access(user, event):
    from django.core.exceptions import PermissionDenied

    if not user_can_manage_event(user, event):
        raise PermissionDenied("You don't have permission to edit this event.")

    return event


class EventScopedQuerysetMixin:
    def filter_events_queryset(self, queryset):
        return get_visible_events(self.request.user, queryset)
