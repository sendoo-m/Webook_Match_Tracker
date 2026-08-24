# operations/views/match_quick_view.py

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.views import View

from matches.models import Match
from operations.permissions import MatchScopedQuerysetMixin

from .helpers import build_dashboard_match_state


class MatchQuickViewView(LoginRequiredMixin, MatchScopedQuerysetMixin, View):
    """Renders a compact "quick view" card for one match - used by the round
    preview cards, the Alerts & Deadlines table, and the Teams strip so a
    match's key data can be shown in a popup instead of navigating away."""

    def get(self, request, pk, *args, **kwargs):
        match = get_object_or_404(
            self.filter_matches_queryset(
                Match.objects.select_related("home_club", "away_club", "venue", "competition")
            ),
            pk=pk,
        )
        card = build_dashboard_match_state(match, now=timezone.localtime())
        html = render_to_string(
            "operations/partials/match_quick_view.html",
            {"match": match, "card": card},
            request=request,
        )
        return HttpResponse(html)
