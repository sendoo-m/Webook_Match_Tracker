# operations/views/spl_report.py

from datetime import date

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from matches.import_export import export_spl_report_xlsx
from matches.models import Match
from operations.permissions import MatchScopedQuerysetMixin

from .helpers import (
    build_spl_report_row,
    get_coordinators_for_matches,
    get_current_round_number,
    get_dashboard_prefetch,
    get_round_date_ranges,
    get_roshan_league_competition,
    get_selectable_clubs,
)


class SPLReportFilterMixin(MatchScopedQuerysetMixin):
    def get_filtered_matches(self, default_round=None, default_min_round=None):
        """default_round: used by SPLApprovalsView so a fresh page load
        opens on exactly the current matchweek. default_min_round: used by
        SPLReportView so a fresh page load starts at the current matchweek
        and includes every round after it (a report should stay
        comprehensive going forward, not narrow to one round) - matches
        with no round number at all are never hidden by this. Both only
        apply when ?round= is entirely absent from the URL; an explicit
        ?round= (including "" from picking "All") always wins, matching the
        same convention used on the dashboards. Only one of the two should
        be passed by any given caller.

        Returns an extra round_default_applied flag (True only when one of
        the two defaults above actually kicked in) so a template can show
        "showing from the current round onward" without confusing it with
        an explicit, empty "All" selection - both otherwise leave
        selected_round == "".
        """
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
        selected_match = self.request.GET.get("match", "")
        selected_coordinator = self.request.GET.get("coordinator", "")

        round_default_applied = False
        if "round" in self.request.GET:
            selected_round = self.request.GET.get("round", "")
            if selected_round:
                matches = matches.filter(round_number=selected_round)
        elif default_round is not None:
            selected_round = str(default_round)
            round_default_applied = True
            matches = matches.filter(round_number=selected_round)
        elif default_min_round is not None:
            selected_round = ""
            round_default_applied = True
            matches = matches.filter(Q(round_number__gte=default_min_round) | Q(round_number__isnull=True))
        else:
            selected_round = ""

        if selected_club:
            matches = matches.filter(home_club_id=selected_club)
        if selected_match:
            matches = matches.filter(pk=selected_match)
        if selected_coordinator:
            matches = matches.filter(home_club__owner_id=selected_coordinator)

        return matches, selected_club, selected_round, selected_coordinator, roshan_competition, round_default_applied


def _spl_report_row_priority(row):
    """Sort key surfacing matches that still need action (an unapproved
    plan, missing KVs, incomplete Webook prep, unsent comp tickets, or low
    readiness) ahead of ones that are already squared away - a flat
    chronological order buries the handful of rows an SPL coordinator
    actually needs to act on among hundreds of already-done ones.
    Finished matches sink to the bottom regardless, since there's nothing
    left to action on them. Ties fall back to event_date (soonest first).
    """
    match = row["match"]
    missing_count = sum([
        not match.ticketing_plan_approved,
        not row["kv_ready"],
        not row["webook_ready"],
        not match.spl_tickets_sent,
    ])
    return (
        row["match_finished"],
        -missing_count,
        row["readiness_percent"],
        match.event_date or date.max,
    )


class SPLReportView(LoginRequiredMixin, SPLReportFilterMixin, TemplateView):
    template_name = "operations/reports/spl_report.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.localtime()

        scoped_matches = self.filter_matches_queryset(Match.objects.all())
        roshan_competition = get_roshan_league_competition()
        if roshan_competition:
            scoped_matches = scoped_matches.filter(competition=roshan_competition)
        current_round_number = get_current_round_number(get_round_date_ranges(scoped_matches), now.date())

        matches, selected_club, selected_round, selected_coordinator, roshan_competition, round_default_applied = (
            self.get_filtered_matches(default_min_round=current_round_number)
        )

        # .order_by("round_number") is required, not decorative: Match's
        # Meta.ordering otherwise leaks into the DISTINCT computation (see
        # SPLApprovalsView for the same fix).
        available_rounds = list(
            scoped_matches.exclude(round_number__isnull=True)
            .values_list("round_number", flat=True).distinct().order_by("round_number")
        )

        # Previous/Next Round navigation. The report defaults to "current
        # round onward" (a range) rather than one round, so there is no
        # selected_round to pin on until the visitor actually clicks
        # Previous/Next - until then, anchor on current_round_number so the
        # navigator still shows something sensible.
        prev_round = None
        next_round = None
        try:
            active_round = int(selected_round) if selected_round else current_round_number
        except ValueError:
            active_round = current_round_number
        if active_round is not None and active_round in available_rounds:
            position = available_rounds.index(active_round)
            if position > 0:
                prev_round = available_rounds[position - 1]
            if position < len(available_rounds) - 1:
                next_round = available_rounds[position + 1]

        rows = [build_spl_report_row(match, now) for match in matches]
        rows.sort(key=_spl_report_row_priority)

        # Triage bar counts, computed before the action filter below so the
        # bar always shows the full picture regardless of which bucket is
        # currently selected (same pattern as Release Schedule's triage bar).
        action_counts = {
            "all": len(rows),
            "not_approved": sum(1 for row in rows if not row["match"].ticketing_plan_approved),
            "not_ready": sum(1 for row in rows if not row["webook_ready"]),
            "not_sent": sum(1 for row in rows if not row["match"].spl_tickets_sent),
        }
        selected_action = self.request.GET.get("action", "")
        if selected_action == "not_approved":
            rows = [row for row in rows if not row["match"].ticketing_plan_approved]
        elif selected_action == "not_ready":
            rows = [row for row in rows if not row["webook_ready"]]
        elif selected_action == "not_sent":
            rows = [row for row in rows if not row["match"].spl_tickets_sent]

        context.update({
            "rows": rows,
            "action_counts": action_counts,
            "selected_action": selected_action,
            "clubs": get_selectable_clubs(scoped_matches),
            "coordinators": get_coordinators_for_matches(scoped_matches),
            "rounds": available_rounds,
            "roshan_competition": roshan_competition,
            "selected_club": selected_club,
            "selected_round": selected_round,
            "selected_coordinator": selected_coordinator,
            # No status filter on this page - round_navigator.html's
            # querystring-preservation references selected_status
            # unconditionally, and an undefined template variable used as a
            # filter argument raises VariableDoesNotExist instead of
            # silently resolving empty, so this must be defined explicitly.
            "selected_status": "",
            "current_round_number": current_round_number,
            "round_default_applied": round_default_applied,
            "prev_round": prev_round,
            "next_round": next_round,
            "match_status": Match.Status,
        })
        return context


class SPLReportExportView(LoginRequiredMixin, SPLReportFilterMixin, View):
    def get(self, request, *args, **kwargs):
        matches, *_ = self.get_filtered_matches()
        now = timezone.localtime()
        rows = [build_spl_report_row(match, now) for match in matches]
        content = export_spl_report_xlsx(rows)
        response = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="spl_report.xlsx"'
        return response
