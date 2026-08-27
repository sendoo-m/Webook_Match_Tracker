from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

from control_panel.forms import ClubForm
from matches.models import Club

from .base import PanelCreateView, PanelListView, PanelToggleActiveView, PanelUpdateView


class TeamListView(PanelListView):
    model = Club
    template_name = "control_panel/club_list.html"
    context_object_name = "clubs"
    ordering = ["name_ar"]
    page_title = _("Teams")
    create_url_name = "control_panel:team-create"
    create_label = _("Add Team")


class TeamCreateView(PanelCreateView):
    model = Club
    form_class = ClubForm
    template_name = "control_panel/club_form.html"
    success_url = reverse_lazy("control_panel:team-list")
    success_message = _("Team created.")
    page_title = _("Add Team")
    list_url_name = "control_panel:team-list"


class TeamUpdateView(PanelUpdateView):
    model = Club
    form_class = ClubForm
    template_name = "control_panel/club_form.html"
    success_url = reverse_lazy("control_panel:team-list")
    success_message = _("Team updated.")
    page_title = _("Edit Team")
    list_url_name = "control_panel:team-list"


class TeamToggleActiveView(PanelToggleActiveView):
    model = Club
    success_url_name = "control_panel:team-list"
