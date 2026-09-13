# control_panel/context_processors.py

from events.permissions import can_manage_events_panel, can_view_events_hub
from operations.permissions import can_manage_control_panel, can_view_own_club_dashboard, is_viewer_only

from .design_tokens import LIGHT_TOKENS
from .models import ReleaseNote


def panel_nav_flag(request):
    user = getattr(request, "user", None)
    latest_release = ReleaseNote.objects.first() if getattr(user, "is_authenticated", False) else None
    return {
        "can_view_control_panel": can_manage_control_panel(user),
        "is_viewer_only": is_viewer_only(user),
        "can_view_own_club_dashboard": can_view_own_club_dashboard(user),
        "latest_release_version": latest_release.version if latest_release else None,
        "can_view_events_hub": can_view_events_hub(user),
        "can_manage_events_panel": can_manage_events_panel(user),
    }


def design_tokens(request):
    """Expose the Figma design tokens (light palette) for inline styles, emails, PDFs, etc.

    Dark/light switching for regular pages is handled entirely in CSS via
    prefers-color-scheme (see static/design_tokens.css), so only the light
    values are needed here.
    """
    return {"tokens": LIGHT_TOKENS}