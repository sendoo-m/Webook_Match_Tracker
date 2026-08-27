from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

from control_panel.forms import VenueForm
from matches.models import Venue

from .base import PanelCreateView, PanelListView, PanelToggleActiveView, PanelUpdateView


class StadiumListView(PanelListView):
    model = Venue
    template_name = "control_panel/venue_list.html"
    context_object_name = "venues"
    ordering = ["name_ar"]
    page_title = _("Stadiums")
    create_url_name = "control_panel:stadium-create"
    create_label = _("Add Stadium")


class StadiumCreateView(PanelCreateView):
    model = Venue
    form_class = VenueForm
    template_name = "control_panel/venue_form.html"
    success_url = reverse_lazy("control_panel:stadium-list")
    success_message = _("Stadium created.")
    page_title = _("Add Stadium")
    list_url_name = "control_panel:stadium-list"


class StadiumUpdateView(PanelUpdateView):
    model = Venue
    form_class = VenueForm
    template_name = "control_panel/venue_form.html"
    success_url = reverse_lazy("control_panel:stadium-list")
    success_message = _("Stadium updated.")
    page_title = _("Edit Stadium")
    list_url_name = "control_panel:stadium-list"


class StadiumToggleActiveView(PanelToggleActiveView):
    model = Venue
    success_url_name = "control_panel:stadium-list"
