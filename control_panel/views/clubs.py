from django.urls import reverse_lazy

from control_panel.forms import ClubForm
from matches.models import Club

from .base import PanelCreateView, PanelListView, PanelToggleActiveView, PanelUpdateView


class TeamListView(PanelListView):
    model = Club
    template_name = "control_panel/club_list.html"
    context_object_name = "clubs"
    ordering = ["name_ar"]
    page_title = "Teams"
    create_url_name = "control_panel:team-create"
    create_label = "Add Team"


class TeamCreateView(PanelCreateView):
    model = Club
    form_class = ClubForm
    template_name = "control_panel/club_form.html"
    success_url = reverse_lazy("control_panel:team-list")
    success_message = "Team created."
    page_title = "Add Team"
    list_url_name = "control_panel:team-list"


class TeamUpdateView(PanelUpdateView):
    model = Club
    form_class = ClubForm
    template_name = "control_panel/club_form.html"
    success_url = reverse_lazy("control_panel:team-list")
    success_message = "Team updated."
    page_title = "Edit Team"
    list_url_name = "control_panel:team-list"


class TeamToggleActiveView(PanelToggleActiveView):
    model = Club
    success_url_name = "control_panel:team-list"
