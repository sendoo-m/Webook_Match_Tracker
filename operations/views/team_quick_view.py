# operations/views/team_quick_view.py

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.views import View

from matches.models import Club, Match
from operations.permissions import MatchScopedQuerysetMixin

from .helpers import build_dashboard_match_state, get_dashboard_prefetch

NEXT_HOME_MATCHES_LIMIT = 6


class TeamQuickViewView(LoginRequiredMixin, MatchScopedQuerysetMixin, View):
    """Clicking a team in the dashboard's Teams strip shows their next
    NEXT_HOME_MATCHES_LIMIT home matches - away fixtures aren't this club's
    own event to manage, matching the same "home only" convention already
    used for match-edit permissions (see user_can_manage_match)."""

    def get(self, request, club_id, *args, **kwargs):
        club = get_object_or_404(Club, pk=club_id)
        today = timezone.localdate()
        now = timezone.localtime()

        candidate_matches = self.filter_matches_queryset(
            Match.objects.filter(home_club=club, event_date__gte=today)
            .select_related("home_club", "away_club", "venue", "competition")
            .prefetch_related(get_dashboard_prefetch())
            .order_by("event_date", "match_start_time")
        )

        cards = []
        for match in candidate_matches:
            card = build_dashboard_match_state(match, now=now)
            if card["is_past"]:
                continue
            cards.append(card)
            if len(cards) >= NEXT_HOME_MATCHES_LIMIT:
                break

        html = render_to_string(
            "operations/partials/team_next_matches_popup.html",
            {"club": club, "cards": cards},
            request=request,
        )
        return HttpResponse(html)
