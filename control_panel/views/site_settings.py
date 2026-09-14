# control_panel/views/site_settings.py

from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

from control_panel.forms import SiteSettingsForm
from control_panel.models import SiteSettings

from .base import PanelUpdateView


class SiteSettingsUpdateView(PanelUpdateView):
    """A singleton settings page - no list, no create, just one update
    view that always operates on SiteSettings.load()'s single row,
    regardless of what's (or isn't) in the URL."""

    model = SiteSettings
    form_class = SiteSettingsForm
    template_name = "control_panel/site_settings_form.html"
    success_url = reverse_lazy("control_panel:site-settings")
    success_message = _("Settings updated.")
    page_title = _("Settings")
    list_url_name = "control_panel:site-settings"

    def get_object(self, queryset=None):
        return SiteSettings.load()
