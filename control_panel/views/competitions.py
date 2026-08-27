from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

from control_panel.forms import CompetitionForm
from matches.models import Competition

from .base import PanelCreateView, PanelListView, PanelToggleActiveView, PanelUpdateView


class SectionListView(PanelListView):
    model = Competition
    template_name = "control_panel/competition_list.html"
    context_object_name = "competitions"
    ordering = ["sort_order", "name_ar"]
    page_title = _("Sections")
    create_url_name = "control_panel:section-create"
    create_label = _("Add Section")


class SectionCreateView(PanelCreateView):
    model = Competition
    form_class = CompetitionForm
    template_name = "control_panel/competition_form.html"
    success_url = reverse_lazy("control_panel:section-list")
    success_message = _("Section created.")
    page_title = _("Add Section")
    list_url_name = "control_panel:section-list"


class SectionUpdateView(PanelUpdateView):
    model = Competition
    form_class = CompetitionForm
    template_name = "control_panel/competition_form.html"
    success_url = reverse_lazy("control_panel:section-list")
    success_message = _("Section updated.")
    page_title = _("Edit Section")
    list_url_name = "control_panel:section-list"


class SectionToggleActiveView(PanelToggleActiveView):
    model = Competition
    success_url_name = "control_panel:section-list"
