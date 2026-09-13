# spl/views/finished_matches.py
#
# "SPL Finished Matches" - a read-only history view for matches SPL
# Approvals no longer shows (it drops finished matches entirely, per
# request). This is where to go back and check whether/when a finished
# match's ticketing plan was approved, its approval file uploaded, and its
# complimentary tickets confirmed sent - no action buttons, since none of
# that can still be done for a match that already happened.
#
# Reuses the same SPLReportFilterMixin/build_spl_report_row plumbing as
# SPLReportView and SPLApprovalsView so all three pages agree on what "a
# match" looks like; unlike SPLApprovalsView it does NOT default to the
# current round (there's no "current" finished round - it's a plain history
# list, newest-finished-first, with normal page-number pagination).
#
# URL: operations:spl-finished-matches. Linked from the SPL Approvals page.

from datetime import time

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.utils import timezone
from django.views.generic import TemplateView

from matches.models import Match

from operations.views.helpers import build_spl_report_row, get_coordinators_for_matches, get_selectable_clubs

from .report import SPLReportFilterMixin


class SPLFinishedMatchesView(LoginRequiredMixin, SPLReportFilterMixin, TemplateView):
    template_name = "operations/spl_finished_matches.html"
    PAGE_SIZE = 20

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.localtime()
        matches, selected_club, selected_round, selected_coordinator, roshan_competition, _round_default_applied = (
            self.get_filtered_matches()
        )
        scoped_matches = self.filter_matches_queryset(Match.objects.all())
        if roshan_competition:
            scoped_matches = scoped_matches.filter(competition=roshan_competition)

        rows = [build_spl_report_row(match, now) for match in matches]
        rows = [row for row in rows if row["match_finished"]]
        rows.sort(
            key=lambda row: (row["match"].event_date, row["match"].match_start_time or time.min),
            reverse=True,
        )

        paginator = Paginator(rows, self.PAGE_SIZE)
        page_obj = paginator.get_page(self.request.GET.get("page", 1))

        context.update({
            "rows": page_obj.object_list,
            "page_obj": page_obj,
            "clubs": get_selectable_clubs(scoped_matches),
            "coordinators": get_coordinators_for_matches(scoped_matches),
            "rounds": scoped_matches.exclude(round_number__isnull=True)
                .values_list("round_number", flat=True).distinct().order_by("round_number"),
            "roshan_competition": roshan_competition,
            "selected_club": selected_club,
            "selected_round": selected_round,
            "selected_coordinator": selected_coordinator,
        })
        return context
