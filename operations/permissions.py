MANAGER_GROUPS = {"Operations Manager", "Super Admin"}


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


def can_view_all_matches(user):
    if not getattr(user, "is_authenticated", False):
        return False

    return user.is_superuser or user.groups.filter(
        name__in=MANAGER_GROUPS
    ).exists()


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
    if not getattr(user, "is_authenticated", False):
        return False

    if can_view_all_matches(user):
        return True

    club_ids = set(get_user_club_ids(user))
    competition_ids = set(get_user_competition_ids(user))
    is_home_match = match.home_club_id in club_ids
    has_competition_access = match.competition_id in competition_ids
    return is_home_match and has_competition_access


def require_match_access(user, match):
    from django.core.exceptions import PermissionDenied

    if not user_can_manage_match(user, match):
        raise PermissionDenied

    return match
