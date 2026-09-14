from django.contrib.auth import get_user_model
from django.utils import timezone

from core.permissions import VIEWER_GROUPS, can_manage_control_panel

from .models import Notification

User = get_user_model()


def notify_users(users, notification_type, message, match=None, plan=None):
    """Create a Notification for each user in `users`, skipping anyone who
    already has one for the exact same (recipient, type, match, plan) -
    this de-dupe lives here (not in the caller) so every call site, including
    a daily sweep that might re-run over the same match, is automatically
    idempotent instead of each caller having to remember to check first."""
    created = []
    seen_recipient_ids = set()
    for user in users:
        if user is None or user.id in seen_recipient_ids:
            continue
        seen_recipient_ids.add(user.id)
        exists = Notification.objects.filter(
            recipient=user,
            notification_type=notification_type,
            match=match,
            plan=plan,
        ).exists()
        if exists:
            continue
        created.append(
            Notification.objects.create(
                recipient=user,
                notification_type=notification_type,
                match=match,
                plan=plan,
                message=message,
            )
        )
    return created


def _spl_recipients():
    """Everyone whose entire access is the read-only Viewer role - mirrors
    core.permissions.is_viewer_only, done as a bulk queryset instead of a
    per-user loop since this is the "SPL" audience for every notification
    type that mentions SPL."""
    return [
        user
        for user in User.objects.filter(groups__name__in=VIEWER_GROUPS, is_active=True).distinct()
        if not can_manage_control_panel(user)
    ]


def notify_spl(notification_type, message, match=None, plan=None):
    return notify_users(_spl_recipients(), notification_type, message, match=match, plan=plan)


def _club_account_holders(club):
    """owner (coordinator) + club_account (direct login) for one club - the
    two independent slots that can both be simultaneously staffed."""
    holders = []
    if club.owner_id:
        holders.append(club.owner)
    if club.club_account_id:
        holders.append(club.club_account)
    return holders


def notify_club(match, notification_type, message):
    """The general "club-side" audience for a match: home_club's owner AND
    club_account (both slots), matching this codebase's split of "who
    represents this club" into a coordinator and the club's own account."""
    return notify_users(_club_account_holders(match.home_club), notification_type, message, match=match)


def notify_coordinator(match, notification_type, message):
    """The internal coordinator only (home_club.owner) - not the club's own
    direct account - matching user_can_manage_match's existing exclusion of
    the club-viewer account from match-management actions."""
    recipients = [match.home_club.owner] if match.home_club.owner_id else []
    return notify_users(recipients, notification_type, message, match=match)


def run_daily_notification_sweep():
    """The one function behind both `manage.py generate_daily_notifications`
    and the request-time fallback in operations/middleware.py - mirrors the
    dual CLI/button pattern matches.calendar_sync already established for
    calendar sync, so there's exactly one place this logic lives.

    Walks every match once and fires, for each: the 25-day club notice, the
    20-day-not-live coordinator notice, and the match-live notice (SPL +
    both clubs). All three go through notify_users, which already skips a
    recipient who has one for this exact (type, match) - so re-running this
    daily, or many times in one day, never re-notifies for the same event.
    Returns a dict of how many new notifications were created per type, for
    the command's own summary output."""
    from matches.models import Match
    from operations.views.helpers import build_dashboard_match_state

    now = timezone.localtime()
    counts = {
        Notification.NotificationType.MATCH_25_DAYS: 0,
        Notification.NotificationType.MATCH_20_DAYS_NOT_LIVE: 0,
        Notification.NotificationType.MATCH_LIVE: 0,
    }
    matches = Match.objects.exclude(event_date=None).select_related("home_club", "away_club")
    for match in matches:
        state = build_dashboard_match_state(match, now)
        days_to_match = state["days_to_match"]
        if days_to_match is None:
            continue

        if days_to_match == 25:
            created = notify_club(
                match,
                Notification.NotificationType.MATCH_25_DAYS,
                f"25 days remain until {match}.",
            )
            counts[Notification.NotificationType.MATCH_25_DAYS] += len(created)

        if days_to_match == 20 and not state["is_live_now"]:
            created = notify_coordinator(
                match,
                Notification.NotificationType.MATCH_20_DAYS_NOT_LIVE,
                f"20 days remain until {match} and it is not live yet.",
            )
            counts[Notification.NotificationType.MATCH_20_DAYS_NOT_LIVE] += len(created)

        if state["is_live_now"]:
            created = notify_match_live(match, f"{match} has gone live.")
            counts[Notification.NotificationType.MATCH_LIVE] += len(created)

    return counts


def notify_match_live(match, message):
    """Match went live: SPL, plus both the home and away clubs' owner and
    club_account - going live affects both sides' spectators, unlike a
    home-only pricing plan submission."""
    recipients = list(_spl_recipients())
    recipients += _club_account_holders(match.home_club)
    if match.away_club_id:
        recipients += _club_account_holders(match.away_club)
    return notify_users(recipients, Notification.NotificationType.MATCH_LIVE, message, match=match)
