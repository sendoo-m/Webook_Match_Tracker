# operations/views/release_schedule.py
#
# "Match Release Schedule" - shows every match's ticket-sale release date
# against the "must go on sale 20 days before kickoff" rule, color-coded
# (green = released on time, red = late/overdue, amber = due today, blue =
# upcoming/not due yet), with a reason attached for WHY a release is late
# (SPL hasn't provided the schedule yet, or a ticket design delay - with
# free-text notes for who's responsible).
#
# Unlike the SPL-only pages (SPL Report/Approvals/Finished Matches), this
# is visible to EVERYONE per request: it reuses MatchScopedQuerysetMixin
# exactly like every other match view in this app, so a Club Manager
# automatically only sees their own club's matches, while Operations
# Manager/Super Admin/the SPL Viewer role see every match - no new
# permission logic needed, just the existing scoping.
#
# URL: operations:release-schedule (page) and
# operations:release-delay-update (the small "set/edit delay reason" POST
# action, permission-gated per match by the same rule as who's allowed to
# manage that match - home club owner, Operations Manager/Super Admin, or
# the SPL Viewer role, since any of the three might be the one who knows
# why a release is late).

from datetime import time

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import TemplateView

from matches.models import Match
from operations.forms import ReleaseDelayForm
from operations.permissions import MatchScopedQuerysetMixin, can_manage_control_panel, user_can_manage_match

from .helpers import (
    compute_release_status,
    get_current_round_number,
    get_round_date_ranges,
    get_roshan_league_competition,
    get_selectable_clubs,
)


def _can_edit_delay_reason(user, match):
    # Club coordinators only, per request - Operations Manager/Super Admin
    # and the SPL Viewer role can still see the reason but no longer edit it.
    if can_manage_control_panel(user):
        return False
    return user_can_manage_match(user, match)


class MatchReleaseScheduleView(LoginRequiredMixin, MatchScopedQuerysetMixin, TemplateView):
    template_name = "operations/release_schedule.html"
    PAGE_SIZE = 30

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()

        matches = self.filter_matches_queryset(
            Match.objects.select_related("home_club", "home_club__owner", "away_club", "venue", "competition")
            .order_by("event_date", "match_start_time", "id")
        )

        selected_club = self.request.GET.get("club", "")
        selected_status = self.request.GET.get("status", "")

        filter_options_matches = matches
        if selected_club:
            matches = matches.filter(home_club_id=selected_club)

        # Round numbers only mean anything for the Roshan League in
        # practice (every other competition either has none or a handful of
        # one-off values) - "current round" is computed from that scope
        # specifically, matching the dashboards. Matches with no round
        # number at all (other competitions) are never hidden by this
        # default, since there's no round to compare them against.
        roshan_competition = get_roshan_league_competition()
        roshan_matches = matches.filter(competition=roshan_competition) if roshan_competition else matches.none()
        current_round_number = get_current_round_number(get_round_date_ranges(roshan_matches), today)

        # "round" absent entirely (a fresh page load) is the ONLY case that
        # applies the current-round-onward default - explicitly picking
        # "All" also leaves selected_round == "" but must NOT re-trigger it,
        # so round_default_applied (not selected_round) is what the template
        # checks to decide whether to show the "from Round N onward" note.
        round_default_applied = "round" not in self.request.GET
        if round_default_applied:
            selected_round = ""
            if current_round_number is not None:
                matches = matches.filter(Q(round_number__gte=current_round_number) | Q(round_number__isnull=True))
        else:
            selected_round = self.request.GET.get("round", "")
            if selected_round:
                matches = matches.filter(round_number=selected_round)
            # else: "All" explicitly chosen - no round restriction at all.

        rows = []
        for match in matches:
            release = compute_release_status(match, today)
            if release["status"] is None:
                continue
            rows.append({
                "match": match,
                "can_edit_reason": _can_edit_delay_reason(self.request.user, match),
                **release,
            })

        # Triage bar counts - computed before the status filter below so the
        # bar always reflects the full picture (within the current
        # Club/Round scope) regardless of which bucket is currently
        # selected, letting the visitor jump straight between buckets.
        triage_counts = {
            "overdue": sum(1 for row in rows if row["status"] in ("delayed", "released_late")),
            "due_today": sum(1 for row in rows if row["status"] == "due_today"),
            "live_missing_release_date": sum(1 for row in rows if row["status"] == "live_missing_release_date"),
            "upcoming": sum(1 for row in rows if row["status"] == "upcoming"),
        }

        if selected_status == "overdue":
            rows = [row for row in rows if row["status"] in ("delayed", "released_late")]
        elif selected_status:
            rows = [row for row in rows if row["status"] == selected_status]

        # .order_by("round_number") is required, not decorative: Match's
        # Meta.ordering otherwise leaks into the DISTINCT computation (see
        # SPLApprovalsView for the same fix).
        available_rounds = list(
            filter_options_matches.exclude(round_number__isnull=True)
            .values_list("round_number", flat=True).distinct().order_by("round_number")
        )

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

        # Most actionable first: overdue and due-today rise to the top,
        # already-released matches sink to the bottom.
        status_priority = {
            "live_missing_release_date": 0,
            "delayed": 1,
            "due_today": 2,
            "upcoming": 3,
            "released_late": 4,
            "released_on_time": 5,
        }
        rows.sort(key=lambda row: (status_priority.get(row["status"], 9), row["match"].event_date, row["match"].match_start_time or time.min))

        # A flat "hundreds of rows, no pagination" table was hard to scan -
        # paginated rather than grouped by round, since the whole point of
        # the priority sort above is surfacing the most actionable rows
        # first *across* rounds, which a per-round accordion would undo.
        paginator = Paginator(rows, self.PAGE_SIZE)
        page_obj = paginator.get_page(self.request.GET.get("page", 1))

        context.update({
            "rows": page_obj.object_list,
            "page_obj": page_obj,
            "row_count": len(rows),
            "triage_counts": triage_counts,
            "clubs": get_selectable_clubs(filter_options_matches),
            "rounds": available_rounds,
            "selected_club": selected_club,
            "selected_round": selected_round,
            "selected_status": selected_status,
            # No coordinator filter on this page - the shared round_navigator
            # partial references selected_coordinator unconditionally, and an
            # undefined template variable used as a filter argument (not just
            # for display) raises VariableDoesNotExist instead of silently
            # resolving empty, so this must be defined explicitly.
            "selected_coordinator": "",
            "current_round_number": current_round_number,
            "round_default_applied": round_default_applied,
            "prev_round": prev_round,
            "next_round": next_round,
            "delay_reason_choices": Match.ReleaseDelayReason.choices,
        })
        return context


class MatchReleaseDelayUpdateView(LoginRequiredMixin, MatchScopedQuerysetMixin, View):
    def post(self, request, pk, *args, **kwargs):
        match = get_object_or_404(self.filter_matches_queryset(Match.objects.all()), pk=pk)
        if not _can_edit_delay_reason(request.user, match):
            raise PermissionDenied("You don't have permission to set this match's delay reason.")

        form = ReleaseDelayForm(request.POST, instance=match)
        if form.is_valid():
            form.save()
            messages.success(request, _("Delay reason updated."))
        else:
            error_text = " ".join(str(error) for errors in form.errors.values() for error in errors)
            messages.error(request, error_text or _("Could not update the delay reason."))

        referer = request.META.get("HTTP_REFERER")
        return redirect(referer or "operations:release-schedule")
