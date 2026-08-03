from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import FormView

from checklists.models import ChecklistTemplateItem, MatchChecklistItem
from control_panel.forms import MatchExportFilterForm, MatchForm, MatchImportForm
from control_panel.permissions import ControlPanelAccessMixin
from matches.import_export import (
    build_import_template_xlsx,
    export_matches_csv,
    export_matches_xlsx,
    import_matches_file,
)
from matches.models import Match

from .base import PanelCreateView, PanelListView, PanelUpdateView


class MatchAdminListView(PanelListView):
    model = Match
    template_name = "control_panel/match_list.html"
    context_object_name = "matches"
    ordering = ["-event_date", "-match_start_time", "-id"]
    page_title = "Matches"
    create_url_name = "control_panel:match-create"
    create_label = "Add Match"

    def get_queryset(self):
        return super().get_queryset().select_related(
            "competition", "home_club", "away_club", "venue"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["export_form"] = MatchExportFilterForm()
        return context


class MatchAdminCreateView(PanelCreateView):
    model = Match
    form_class = MatchForm
    template_name = "control_panel/match_form.html"
    success_url = reverse_lazy("control_panel:match-list")
    success_message = "Match created."
    page_title = "Add Match"
    list_url_name = "control_panel:match-list"

    def form_valid(self, form):
        response = super().form_valid(form)
        active_templates = ChecklistTemplateItem.objects.filter(is_active=True)
        MatchChecklistItem.objects.bulk_create(
            [
                MatchChecklistItem(match=self.object, template_item=template)
                for template in active_templates
            ]
        )
        return response


class MatchAdminUpdateView(PanelUpdateView):
    model = Match
    form_class = MatchForm
    template_name = "control_panel/match_form.html"
    success_url = reverse_lazy("control_panel:match-list")
    success_message = "Match updated."
    page_title = "Edit Match"
    list_url_name = "control_panel:match-list"


class MatchExportView(LoginRequiredMixin, ControlPanelAccessMixin, View):
    def get(self, request, *args, **kwargs):
        queryset = Match.objects.all()
        competition_id = request.GET.get("competition")
        if competition_id:
            queryset = queryset.filter(competition_id=competition_id)

        if request.GET.get("format") == "csv":
            content = export_matches_csv(queryset)
            response = HttpResponse(content, content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = 'attachment; filename="matches_export.csv"'
        else:
            content = export_matches_xlsx(queryset)
            response = HttpResponse(
                content,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = 'attachment; filename="matches_export.xlsx"'
        return response


class MatchTemplateView(LoginRequiredMixin, ControlPanelAccessMixin, View):
    def get(self, request, *args, **kwargs):
        content = build_import_template_xlsx()
        response = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="matches_import_template.xlsx"'
        return response


class MatchImportView(LoginRequiredMixin, ControlPanelAccessMixin, FormView):
    template_name = "control_panel/match_import.html"
    form_class = MatchImportForm

    def get_success_url(self):
        return reverse("control_panel:match-import")

    def form_valid(self, form):
        import_file = form.cleaned_data["import_file"]
        competition = form.cleaned_data.get("competition")
        result = import_matches_file(
            import_file, import_file.name, competition.id if competition else None
        )
        return self.render_to_response(self.get_context_data(form=self.form_class(), result=result))
