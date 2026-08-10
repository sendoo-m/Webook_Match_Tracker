# operations/views/spl_report.py

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.views import View
from django.views.generic import TemplateView

from matches.import_export import export_spl_report_xlsx
from matches.models import Club, Competition, Match
from operations.permissions import MatchScopedQuerysetMixin

from .helpers import build_spl_report_row, get_dashboard_prefetch


class SPLReportFilterMixin(MatchScopedQuerysetMixin):
    def get_filtered_matches(self):
        matches = self.filter_matches_queryset(
            Match.objects.select_related("home_club", "home_club__owner", "away_club", "venue", "competition")
            .prefetch_related(get_dashboard_prefetch())
            .order_by("event_date", "match_start_time", "id")
        )

        selected_club = self.request.GET.get("club", "")
        selected_competition = self.request.GET.get("competition", "")
        selected_round = self.request.GET.get("round", "")

        if selected_club:
            matches = matches.filter(home_club_id=selected_club)
        if selected_competition:
            matches = matches.filter(competition_id=selected_competition)
        if selected_round:
            matches = matches.filter(round_number=selected_round)

        return matches, selected_club, selected_competition, selected_round


class SPLReportView(LoginRequiredMixin, SPLReportFilterMixin, TemplateView):
    template_name = "operations/reports/spl_report.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        matches, selected_club, selected_competition, selected_round = self.get_filtered_matches()
        scoped_matches = self.filter_matches_queryset(Match.objects.all())

        context.update({
            "rows": [build_spl_report_row(match) for match in matches],
            "clubs": Club.objects.filter(
                is_active=True, id__in=scoped_matches.values_list("home_club_id", flat=True)
            ).distinct().order_by("name_ar"),
            "competitions": Competition.objects.filter(
                is_active=True, id__in=scoped_matches.values_list("competition_id", flat=True)
            ).distinct().order_by("sort_order", "name_ar"),
            "rounds": scoped_matches.exclude(round_number__isnull=True)
                .values_list("round_number", flat=True).distinct().order_by("round_number"),
            "selected_club": selected_club,
            "selected_competition": selected_competition,
            "selected_round": selected_round,
        })
        return context


class SPLReportExportView(LoginRequiredMixin, SPLReportFilterMixin, View):
    def get(self, request, *args, **kwargs):
        matches, *_ = self.get_filtered_matches()
        rows = [build_spl_report_row(match) for match in matches]
        content = export_spl_report_xlsx(rows)
        response = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="spl_report.xlsx"'
        return response
