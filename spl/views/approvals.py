# operations/views/spl_approvals.py
#
# "SPL Approvals" - a dedicated page for the two SPL-team write actions
# (confirm the ticketing plan + upload its approval file, confirm
# complimentary tickets were sent) that used to live inside the SPL Report
# table. Moved out per request: the report is meant to be a read-mostly
# overview, and cramming Confirm buttons + a file upload form into a table
# cell made the report cluttered. Reuses the exact same filtered queryset
# and row-shape as SPLReportView (SPLReportFilterMixin, build_spl_report_row)
# so both pages always agree on which matches/fields are in scope.
#
# Two more rules on top of that shared base, both per request:
#   - Finished matches are dropped entirely, regardless of their plan/ticket
#     flags - once a match has happened there is nothing left to approve,
#     so leaving it in this list (unapproved or not) is just noise.
#   - Opens on the CURRENT matchweek by default (same
#     get_current_round_number/get_round_date_ranges logic as the
#     dashboards), showing one round at a time with Previous/Next Round
#     pagination instead of every round's cards at once.
#
# URL: operations:spl-approvals (see operations/urls.py). Linked from the
# sidebar (templates/operations/base.html, next to "SPL Report") and from
# the SPL Report page's own read-only status badges.

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.views.generic import TemplateView

from matches.models import Match
from operations.permissions import can_access_spl_approval_area, can_manage_control_panel, is_viewer_only

from .helpers import (
    build_spl_report_row,
    get_coordinators_for_matches,
    get_current_round_number,
    get_round_date_ranges,
    get_roshan_league_competition,
    get_selectable_clubs,
)
from .spl_report import SPLReportFilterMixin


class SPLApprovalsView(LoginRequiredMixin, SPLReportFilterMixin, TemplateView):
    """SPL approval data (ticketing plan status, approval file, complimentary
    tickets) is Viewer/manager territory only - a Club Manager account (or
    anyone else without one of those two roles) has never been meant to see
    this page, even read-only. LoginRequiredMixin alone only checked they
    were logged in, not that they held one of those roles, so a club user
    could open this page directly (writes were already blocked, but the page
    itself wasn't). can_access_spl_approval_area is the same check
    SPLPlanConfirmView/SPLTicketsConfirmView/SPLPlanApprovalUploadView already
    perform inline for their own POST actions - centralizing it here doesn't
    change what those views do, it just closes the read-side gap on this one
    page. Runs before get_context_data, so an unauthorized request never
    reaches the query that builds the row data."""

    template_name = "operations/spl_approvals.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not can_access_spl_approval_area(request.user):
            raise PermissionDenied("This page isn't available to your account.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.localtime()

        # Round availability/ranges are a global fact about the league, not
        # affected by the club/coordinator filters below, so this is computed
        # from the full scoped queryset rather than the filtered one.
        scoped_matches = self.filter_matches_queryset(Match.objects.all())
        roshan_competition = get_roshan_league_competition()
        if roshan_competition:
            scoped_matches = scoped_matches.filter(competition=roshan_competition)

        round_date_ranges = get_round_date_ranges(scoped_matches)
        current_round_number = get_current_round_number(round_date_ranges, now.date())

        matches, selected_club, selected_round, selected_coordinator, roshan_competition, _round_default_applied = (
            self.get_filtered_matches(default_round=current_round_number)
        )

        can_confirm = is_viewer_only(self.request.user) or can_manage_control_panel(self.request.user)

        rows = [build_spl_report_row(match, now) for match in matches]
        rows = [row for row in rows if not row["match_finished"]]

        # .order_by("round_number") is required, not decorative: Match's
        # Meta.ordering (event_date, match_start_time, id) otherwise leaks
        # into the DISTINCT computation and "distinct" round numbers come
        # back repeated once per differing event_date.
        available_rounds = list(
            scoped_matches.exclude(round_number__isnull=True)
            .values_list("round_number", flat=True).distinct().order_by("round_number")
        )

        # Previous/Next Round pagination - only meaningful when one specific
        # round is selected (not "All"), which is the default state.
        prev_round = None
        next_round = None
        try:
            selected_round_int = int(selected_round) if selected_round else None
        except ValueError:
            selected_round_int = None
        if selected_round_int is not None and selected_round_int in available_rounds:
            position = available_rounds.index(selected_round_int)
            if position > 0:
                prev_round = available_rounds[position - 1]
            if position < len(available_rounds) - 1:
                next_round = available_rounds[position + 1]

        context.update({
            "rows": rows,
            "clubs": get_selectable_clubs(scoped_matches),
            "coordinators": get_coordinators_for_matches(scoped_matches),
            "rounds": available_rounds,
            "roshan_competition": roshan_competition,
            "selected_club": selected_club,
            "selected_round": selected_round,
            "selected_coordinator": selected_coordinator,
            # No status filter on this page - see the identical note in
            # spl_report.py's context (round_navigator.html needs this
            # defined even when empty).
            "selected_status": "",
            "current_round_number": current_round_number,
            "prev_round": prev_round,
            "next_round": next_round,
            "can_confirm_spl_plan": can_confirm,
            "can_confirm_spl_tickets": can_confirm,
        })
        return context
