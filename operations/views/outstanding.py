from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView

from matches.models import Match
from operations.permissions import MatchScopedQuerysetMixin

from .helpers import build_match_detail_side_context


class MatchOutstandingItemsView(LoginRequiredMixin, MatchScopedQuerysetMixin, DetailView):
    model = Match
    template_name = "operations/match_outstanding.html"
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
        context["match_status"] = Match.Status
        context.update(build_match_detail_side_context(self.object, selected_filter="open"))
        context["outstanding_count"] = sum(
            len(items) for items in context["grouped_checklist"].values()
        )
        return context