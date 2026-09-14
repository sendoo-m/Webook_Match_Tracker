# control_panel/context_processors.py

from core.permissions import can_manage_control_panel, is_club_viewer, is_viewer_only
from events.permissions import can_manage_events_panel, can_view_events_hub
from operations.permissions import can_view_own_club_dashboard, get_owned_club_ids

from .design_tokens import LIGHT_TOKENS
from .models import ReleaseNote, SiteSettings


def panel_nav_flag(request):
    user = getattr(request, "user", None)
    latest_release = ReleaseNote.objects.first() if getattr(user, "is_authenticated", False) else None
    is_full_admin = can_manage_control_panel(user)
    return {
        "can_view_control_panel": is_full_admin,
        # A Club Manager coordinator (owns a club, but isn't a full admin)
        # gets sidebar links straight to their own three scoped Control
        # Panel sections (Matches, Venue Images, Venue Categories) instead
        # of the full "Control panel" link/subnav, which would otherwise
        # show them many sections they have no access to.
        "is_scoped_club_manager": not is_full_admin and bool(get_owned_club_ids(user)),
        "is_viewer_only": is_viewer_only(user),
        "is_club_viewer": is_club_viewer(user),
        "can_view_own_club_dashboard": can_view_own_club_dashboard(user),
        "latest_release_version": latest_release.version if latest_release else None,
        "can_view_events_hub": can_view_events_hub(user),
        "can_manage_events_panel": can_manage_events_panel(user),
        "site_settings": SiteSettings.load(),
    }


def design_tokens(request):
    """Expose the Figma design tokens (light palette) for inline styles, emails, PDFs, etc.

    Dark/light switching for regular pages is handled entirely in CSS via
    prefers-color-scheme (see static/design_tokens.css), so only the light
    values are needed here.
    """
    return {"tokens": LIGHT_TOKENS}