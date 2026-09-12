# operations/views/match_detail.py

from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.views.generic import DetailView

from matches.models import Match
from operations.permissions import (
    MatchScopedQuerysetMixin,
    can_manage_control_panel,
    user_can_manage_match,
)

from .helpers import build_match_detail_side_context, build_spl_report_row


class MatchDetailView(LoginRequiredMixin, MatchScopedQuerysetMixin, DetailView):
    model = Match
    template_name = "operations/match_detail.html"
    context_object_name = "match"

    def get_queryset(self):
        queryset = Match.objects.select_related(
            "home_club",
            "away_club",
            "venue",
            "sent_to_cms_by",
        )
        return self.filter_matches_queryset(queryset)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_filter = self.request.GET.get("filter", "open")
        context["match_status"] = Match.Status
        context["today"] = timezone.localdate()
        context["active_tab"] = "overview"

        # can_edit is per-MATCH: a Club Manager can edit their own home
        # fixtures but not someone else's, an Operations Manager can see
        # this page but not edit it, and Super Admin can edit anything.
        context["can_edit"] = user_can_manage_match(self.request.user, self.object)

        # Slug editing stays a Control Panel-tier action (see operations/views/slug.py),
        # separate from the day-to-day checklist/CMS permission above.
        context["can_edit_slug"] = can_manage_control_panel(self.request.user)

        context.update(build_match_detail_side_context(self.object, selected_filter=selected_filter))
        context.update(build_spl_report_row(self.object, timezone.localtime()))
        return context