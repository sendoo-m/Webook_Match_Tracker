
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView

from matches.models import Match
from operations.permissions import MatchScopedQuerysetMixin, can_view_all_matches

from .helpers import build_match_detail_side_context


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
        selected_filter = self.request.GET.get("filter", "all")
        context["match_status"] = Match.Status
        context["can_edit_slug"] = can_view_all_matches(self.request.user)
        context.update(build_match_detail_side_context(self.object, selected_filter=selected_filter))
        return context
