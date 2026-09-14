# operations/permissions.py
#
# Match/Club/Competition-scoped access rules. The domain-agnostic role
# checks (can_manage_control_panel, is_super_admin, is_viewer_only, and the
# group-name constants they use) now live in core/permissions.py - imported
# and re-exported here unchanged so every existing
# `from operations.permissions import can_manage_control_panel` (and
# similar) elsewhere in the project keeps working without any changes.

from core.permissions import (  # noqa: F401 - re-exported for backward compatibility
    MANAGER_GROUPS,
    VIEWER_GROUPS,
    can_manage_control_panel,
    is_club_viewer,
    is_super_admin,
    is_viewer_only,
)


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


class ExcludeViewerAccessMixin:
    """Blocks the read-only Viewer role from a view entirely (e.g. Missing
    Operational Requirements, which is operations-internal - the SPL team's
    equivalent is the SPL Report). Everyone else passes through unchanged."""

    permission_denied_message = "This report isn't available to Viewer accounts - see the SPL Report instead."

    def dispatch(self, request, *args, **kwargs):
        if is_viewer_only(request.user):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied(self.permission_denied_message)
        return super().dispatch(request, *args, **kwargs)


class ExcludeClubViewerAccessMixin:
    """Blocks accounts in the "Club Viewer" group from a view entirely -
    the Operations Dashboard, the full Events/match list, and the Missing
    Requirements report are operations-internal pages, not meant for the
    real football-club audience, who have their own dedicated Club
    Dashboard instead. Deliberately targets "Club Viewer", not "Club
    Manager" (coordinators) - see is_club_viewer's docstring for why the
    two are kept separate. Everyone else passes through unchanged."""

    permission_denied_message = "This page isn't available to Club Viewer accounts - see the Club Dashboard instead."

    def dispatch(self, request, *args, **kwargs):
        if is_club_viewer(request.user):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied(self.permission_denied_message)
        return super().dispatch(request, *args, **kwargs)


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


def can_manage_home_match(user, match):
    """
    True if this user's own club is the HOME club for this match AND
    they've been granted access to its competition - the same "home +
    competition" rule user_can_manage_match has always used, pulled out
    on its own so both the existing operations views and the club
    dashboard being built on top of it (Phase 3+) share one definition
    instead of each re-deriving it. Deliberately excludes the superuser
    bypass - that's a separate, stronger grant layered on top by callers
    that need it (see user_can_manage_match), not part of "is this club
    the home club" itself.
    """
    if not getattr(user, "is_authenticated", False):
        return False

    club_ids = set(get_user_club_ids(user))
    competition_ids = set(get_user_competition_ids(user))
    is_home_match = match.home_club_id in club_ids
    has_competition_access = match.competition_id in competition_ids
    return is_home_match and has_competition_access


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
      that competition — see can_manage_home_match.
    """
    if not getattr(user, "is_authenticated", False):
        return False

    if user.is_superuser:
        return True

    return can_manage_home_match(user, match)


def require_match_access(user, match):
    from django.core.exceptions import PermissionDenied

    if not user_can_manage_match(user, match):
        raise PermissionDenied("You don't have permission to edit this match.")

    return match


# --- Club Dashboard permission rules (Phase 2) ---------------------------
#
# Everything below is new, additive scaffolding for the club-facing
# dashboard being built in later phases. None of it is wired into any
# existing view yet (Phase 3+ will do that) and none of it changes the
# meaning of get_visible_matches/user_can_manage_match above - those two
# keep governing today's Operations Dashboard exactly as before. A club
# user's own club is still found the same way as everywhere else in this
# module: get_user_club_ids(user), i.e. Club.owner.


def can_view_own_club_dashboard(user):
    """True if this user owns at least one active club - the basic gate
    for the future club dashboard existing at all for them."""
    return bool(get_user_club_ids(user))


def can_view_club_match(user, match):
    """True if this user's club is either side of the fixture (home OR
    away) - broader than can_manage_home_match on purpose, since a club
    dashboard needs to show a club its away fixtures too (read-only),
    not just the ones it operationally runs. Does not affect
    get_visible_matches, which stays home-club-only for every existing
    page."""
    if not getattr(user, "is_authenticated", False):
        return False

    club_ids = set(get_user_club_ids(user))
    return match.home_club_id in club_ids or match.away_club_id in club_ids


def can_upload_home_match_pricing_plan(user, match):
    """True only if this is a home match for the user's club, that match's
    plan isn't already SPL-approved (ticketing_plan_approved locks further
    uploads, same as the field's existing meaning), and it's not already
    past the point of being a going concern (SENT_TO_CMS/PUBLISHED, mirroring
    the freeze rule Match.refresh_checklist_status already applies to
    checklist edits).

    Provisional: there's no separate club-pricing-plan model yet (Phase 5),
    so this reuses the one file field that exists today
    (Match.plan_approval_file). Tightens once that model exists.
    """
    from matches.models import Match

    if not can_manage_home_match(user, match):
        return False

    if match.ticketing_plan_approved:
        return False

    return match.cms_status not in {Match.Status.SENT_TO_CMS, Match.Status.PUBLISHED}


def _current_pricing_plan(match):
    return match.club_pricing_plans.order_by("-version").first()


def can_submit_home_match_to_spl(user, match):
    """True only if this is a home match for the user's club AND its
    current (highest-version) ClubPricingPlan exists and is still in the
    UPLOADED state - submitting is a one-way move to SUBMITTED_TO_SPL, so
    once it's past that state this returns False (already submitted,
    resubmission isn't this function's job)."""
    if not can_manage_home_match(user, match):
        return False

    plan = _current_pricing_plan(match)
    return plan is not None and plan.status == plan.Status.UPLOADED


def can_confirm_home_match_submission(user, match):
    """True only if this is a home match for the user's club AND its
    current plan has actually been submitted (SUBMITTED_TO_SPL) and not
    already confirmed. Still has nothing to do with SPL's own decision -
    ticketing_plan_approved is untouched by any of this."""
    if not can_manage_home_match(user, match):
        return False

    plan = _current_pricing_plan(match)
    return plan is not None and plan.status == plan.Status.SUBMITTED_TO_SPL


def can_access_spl_approval_area(user):
    """True only for the two roles that have ever been able to touch SPL
    approval data: the read-only Viewer team and Operations Manager/Super
    Admin. Identical to the check SPLApprovalsView/spl_confirm.py's views
    already perform inline - centralized here so both call one function
    instead of repeating the same two conditions."""
    return is_viewer_only(user) or can_manage_control_panel(user)


def can_approve_pricing_plan(user, match):
    """Always False for a pure club user, regardless of home/away -
    approving a pricing plan is exclusively an SPL/manager action. The
    match argument exists for a consistent call signature with the other
    can_* functions here, not because home/away changes the answer."""
    return can_access_spl_approval_area(user)


def can_publish_match_from_club_dashboard(user, match):
    """Always False for a pure club user, regardless of home/away - the
    future club dashboard never exposes a way to change cms_status or
    publish a match, on any of its own matches. This does NOT affect the
    existing Operations Dashboard's CMS Status Control, which keeps using
    user_can_manage_match exactly as it does today; this function only
    governs what the new club-facing surface is allowed to show/do."""
    return can_manage_control_panel(user)