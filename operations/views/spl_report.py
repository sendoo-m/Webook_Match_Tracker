# operations/views/spl_report.py

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.views import View
from django.views.generic import TemplateView

from matches.import_export import export_spl_report_xlsx
from matches.models import Club, Match
from operations.permissions import MatchScopedQuerysetMixin, can_manage_control_panel, is_viewer_only

from .helpers import build_spl_report_row, get_coordinators_for_matches, get_dashboard_prefetch, get_roshan_league_competition


class SPLReportFilterMixin(MatchScopedQuerysetMixin):
    def get_filtered_matches(self):
        matches = self.filter_matches_queryset(
            Match.objects.select_related("home_club", "home_club__owner", "away_club", "venue", "competition")
            .prefetch_related(get_dashboard_prefetch())
            .order_by("event_date", "match_start_time", "id")
        )

        # This report is entirely an SPL/Roshan League concern - the other
        # competitions (King Cup, Asian Cup, U21, Friendlies) don't carry SPL
        # ticketing requirements, so the competition scope is fixed rather
        # than a real filter choice.
        roshan_competition = get_roshan_league_competition()
        if roshan_competition:
            matches = matches.filter(competition=roshan_competition)

        selected_club = self.request.GET.get("club", "")
        selected_round = self.request.GET.get("round", "")
        selected_match = self.request.GET.get("match", "")
        selected_coordinator = self.request.GET.get("coordinator", "")

        if selected_club:
            matches = matches.filter(home_club_id=selected_club)
        if selected_round:
            matches = matches.filter(round_number=selected_round)
        if selected_match:
            matches = matches.filter(pk=selected_match)
        if selected_coordinator:
            matches = matches.filter(home_club__owner_id=selected_coordinator)

        return matches, selected_club, selected_round, selected_coordinator, roshan_competition


class SPLReportView(LoginRequiredMixin, SPLReportFilterMixin, TemplateView):
    template_name = "operations/reports/spl_report.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        matches, selected_club, selected_round, selected_coordinator, roshan_competition = self.get_filtered_matches()
        scoped_matches = self.filter_matches_queryset(Match.objects.all())
        if roshan_competition:
            scoped_matches = scoped_matches.filter(competition=roshan_competition)

        context.update({
            "rows": [build_spl_report_row(match) for match in matches],
            "clubs": Club.objects.filter(
                is_active=True, id__in=scoped_matches.values_list("home_club_id", flat=True)
            ).distinct().order_by("name_ar"),
            "coordinators": get_coordinators_for_matches(scoped_matches),
            "rounds": scoped_matches.exclude(round_number__isnull=True)
                .values_list("round_number", flat=True).distinct().order_by("round_number"),
            "roshan_competition": roshan_competition,
            "selected_club": selected_club,
            "selected_round": selected_round,
            "selected_coordinator": selected_coordinator,
            "can_confirm_spl_plan": is_viewer_only(self.request.user) or can_manage_control_panel(self.request.user),
            "can_confirm_spl_tickets": is_viewer_only(self.request.user) or can_manage_control_panel(self.request.user),
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
