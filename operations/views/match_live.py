from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.views.generic import DetailView

from checklists.models import MatchChecklistItem
from matches.models import Match
from operations.permissions import MatchScopedQuerysetMixin

from .helpers import (
    POST_MATCH_CATEGORY_NAME,
    build_dashboard_match_state,
    get_match_activity_page_context,
)


class MatchLiveView(LoginRequiredMixin, MatchScopedQuerysetMixin, DetailView):
    model = Match
    template_name = "operations/match_live.html"
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
        match = self.object
        now = timezone.localtime()

        active_items = list(
            match.checklist_items.select_related("template_item__category", "completed_by")
            .filter(is_active=True)
        )
        attention_items = sorted(
            (
                item for item in active_items
                if item.status != MatchChecklistItem.Status.DONE
                and (
                    item.template_item.category.name == POST_MATCH_CATEGORY_NAME
                    or item.status == MatchChecklistItem.Status.DELAYED
                )
            ),
            key=lambda item: (
                0 if item.status == MatchChecklistItem.Status.DELAYED else 1,
                item.template_item.category.sort_order,
                item.template_item.sort_order,
                item.id,
            ),
        )

        context.update(build_dashboard_match_state(match, now=now))
        context["match_status"] = Match.Status
        context["attention_items"] = attention_items
        context.update(get_match_activity_page_context(match, page=1))
        return context