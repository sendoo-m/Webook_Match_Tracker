# operations/permissions.py

MANAGER_GROUPS = {"Operations Manager", "Super Admin"}
VIEWER_GROUPS = {"Viewer"}


def get_user_club_ids(user):
    if not getattr(user, "is_authenticated", False):
        return []

    if not hasattr(user, "owned_clubs"):
        return []

    return list(
        user.owned_clubs.filter(is_active=True).values_list("id", flat=True)
    )


def get_user_competition_ids(user):
    if not getattr(user, "is_authenticated", False):
        return []

    from matches.models import UserCompetitionAccess

    return list(
        UserCompetitionAccess.objects.filter(user=user).values_list("competition_id", flat=True)
    )


def can_manage_control_panel(user):
    """
    True for users allowed into the Control Panel (Operations Manager /
    Super Admin): full back-office CRUD over clubs, venues, competitions,
    users, and checklist templates — everything except Django's own /admin/.

    This is ONLY about Control Panel access. It does NOT mean the user can
    edit a match's checklist/CMS status in the operations app — see
    user_can_manage_match for that.
    """
    if not getattr(user, "is_authenticated", False):
        return False

    return user.is_superuser or user.groups.filter(
        name__in=MANAGER_GROUPS
    ).exists()


def can_view_all_matches(user):
    """
    True for users allowed to SEE every match across every club and
    competition — managers AND read-only viewers. Do not use this to gate
    write actions.
    """
    if not getattr(user, "is_authenticated", False):
        return False

    if can_manage_control_panel(user):
        return True

    return user.groups.filter(name__in=VIEWER_GROUPS).exists()


def get_visible_matches(user, queryset):
    if not getattr(user, "is_authenticated", False):
        return queryset.none()

    if can_view_all_matches(user):
        return queryset

    club_ids = get_user_club_ids(user)
    competition_ids = get_user_competition_ids(user)
    if not club_ids or not competition_ids:
        return queryset.none()

    return (
        queryset.filter(home_club_id__in=club_ids)
        .filter(competition_id__in=competition_ids)
        .distinct()
    )


class MatchScopedQuerysetMixin:
    def filter_matches_queryset(self, queryset):
        return get_visible_matches(self.request.user, queryset)


def user_can_manage_match(user, match):
    """
    True if this user can perform match-level actions (checklist updates,
    send-to-CMS, CMS status changes) on THIS specific match.

    - Super Admin: always.
    - Operations Manager: NOT included here on purpose. They get full
      visibility and full Control Panel access, but day-to-day checklist/CMS
      work on a match is reserved for the owning Club Manager (or Super
      Admin) — see can_manage_control_panel for their actual scope.
    - Everyone else (Club Manager, or any user with club ownership): only
      for matches where their club is the HOME club (an away fixture for
      their own club does not count) and they've been granted access to
      that competition.
    """
    if not getattr(user, "is_authenticated", False):
        return False

    if user.is_superuser:
        return True

    club_ids = set(get_user_club_ids(user))
    competition_ids = set(get_user_competition_ids(user))
    is_home_match = match.home_club_id in club_ids
    has_competition_access = match.competition_id in competition_ids
    return is_home_match and has_competition_access


def require_match_access(user, match):
    from django.core.exceptions import PermissionDenied

    if not user_can_manage_match(user, match):
        raise PermissionDenied("You don't have permission to edit this match.")

    return match