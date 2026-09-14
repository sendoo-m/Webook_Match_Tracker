from django.contrib.auth import get_user_model

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


def notify_match_live(match, message):
    """Match went live: SPL, plus both the home and away clubs' owner and
    club_account - going live affects both sides' spectators, unlike a
    home-only pricing plan submission."""
    recipients = list(_spl_recipients())
    recipients += _club_account_holders(match.home_club)
    if match.away_club_id:
        recipients += _club_account_holders(match.away_club)
    return notify_users(recipients, Notification.NotificationType.MATCH_LIVE, message, match=match)
