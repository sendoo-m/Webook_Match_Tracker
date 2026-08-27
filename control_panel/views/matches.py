from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import HttpResponse
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import FormView

from checklists.services import attach_default_checklist_items
from control_panel.forms import MatchExportFilterForm, MatchForm, MatchImportForm
from control_panel.permissions import ControlPanelAccessMixin
from matches.import_export import (
    build_import_template_xlsx,
    export_matches_csv,
    export_matches_xlsx,
    import_matches_file,
)
from matches.models import Club, Match, Venue

from .base import PanelCreateView, PanelListView, PanelUpdateView


class MatchAdminListView(PanelListView):
    model = Match
    template_name = "control_panel/match_list.html"
    context_object_name = "matches"
    ordering = ["-event_date", "-match_start_time", "-id"]
    page_title = _("Matches")
    create_url_name = "control_panel:match-create"
    create_label = _("Add Match")

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            "competition", "home_club", "away_club", "venue"
        )
        round_number = self.request.GET.get("round", "")
        club_id = self.request.GET.get("club", "")
        city = self.request.GET.get("city", "")
        if round_number:
            queryset = queryset.filter(round_number=round_number)
        if club_id:
            queryset = queryset.filter(Q(home_club_id=club_id) | Q(away_club_id=club_id))
        if city:
            queryset = queryset.filter(venue__city=city)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["export_form"] = MatchExportFilterForm()
        context["selected_round"] = self.request.GET.get("round", "")
        context["selected_club"] = self.request.GET.get("club", "")
        context["selected_city"] = self.request.GET.get("city", "")
        context["rounds"] = (
            Match.objects.exclude(round_number__isnull=True)
            .values_list("round_number", flat=True).distinct().order_by("round_number")
        )
        context["clubs"] = Club.objects.filter(is_active=True).order_by("name_ar")
        context["cities"] = (
            Venue.objects.exclude(city="").values_list("city", flat=True).distinct().order_by("city")
        )
        return context


class MatchAdminCreateView(PanelCreateView):
    model = Match
    form_class = MatchForm
    template_name = "control_panel/match_form.html"
    success_url = reverse_lazy("control_panel:match-list")
    success_message = _("Match created.")
    page_title = _("Add Match")
    list_url_name = "control_panel:match-list"

    def form_valid(self, form):
        response = super().form_valid(form)
        attach_default_checklist_items(self.object)
        return response


class MatchAdminUpdateView(PanelUpdateView):
    model = Match
    form_class = MatchForm
    template_name = "control_panel/match_form.html"
    success_url = reverse_lazy("control_panel:match-list")
    success_message = _("Match updated.")
    page_title = _("Edit Match")
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
