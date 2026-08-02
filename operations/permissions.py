from django.db.models import Q

MANAGER_GROUPS = {"Club Manager", "Operations Manager", "Super Admin"}


def get_user_club_ids(user):
    if not getattr(user, "is_authenticated", False):
        return []

    if not hasattr(user, "owned_clubs"):
        return []

    return list(
        user.owned_clubs.filter(is_active=True).values_list("id", flat=True)
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
    if not club_ids:
        return queryset.none()

    return queryset.filter(
        Q(home_club_id__in=club_ids) | Q(away_club_id__in=club_ids)
    ).distinct()


class MatchScopedQuerysetMixin:
    def filter_matches_queryset(self, queryset):
        return get_visible_matches(self.request.user, queryset)


def user_can_manage_match(user, match):
    if not getattr(user, "is_authenticated", False):
        return False

    if can_view_all_matches(user):
        return True

    club_ids = set(get_user_club_ids(user))
    return match.home_club_id in club_ids or match.away_club_id in club_ids


def require_match_access(user, match):
    from django.core.exceptions import PermissionDenied

    if not user_can_manage_match(user, match):
        raise PermissionDenied

    return match
    
# # operations/permissions.py

# from django.db.models import Q

# from matches.models import Match


# FULL_ACCESS_GROUPS = {"Operations Director"}


# def user_has_full_match_access(user):
#     if not user.is_authenticated:
#         return False

#     if user.is_superuser:
#         return True

#     return user.groups.filter(name__in=FULL_ACCESS_GROUPS).exists()


# def get_visible_matches(user):
#     if not user.is_authenticated:
#         return Match.objects.none()

#     if user_has_full_match_access(user):
#         return Match.objects.all()

#     return Match.objects.filter(
#         Q(home_club__owner=user) | Q(away_club__owner=user)
#     ).distinct()