from operations.permissions import can_view_all_matches

from .design_tokens import LIGHT_TOKENS


def panel_nav_flag(request):
    return {"can_view_control_panel": can_view_all_matches(getattr(request, "user", None))}


def design_tokens(request):
    """Expose the Figma design tokens (light palette) for inline styles, emails, PDFs, etc.

    Dark/light switching for regular pages is handled entirely in CSS via
    prefers-color-scheme (see static/design_tokens.css), so only the light
    values are needed here.
    """
    return {"tokens": LIGHT_TOKENS}
