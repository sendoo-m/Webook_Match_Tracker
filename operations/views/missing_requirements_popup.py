# operations/views/missing_requirements_popup.py

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.views import View

from matches.models import Match
from operations.permissions import ExcludeViewerAccessMixin, MatchScopedQuerysetMixin

from .helpers import get_missing_requirements_pending_items


class MissingRequirementsPopupView(LoginRequiredMixin, ExcludeViewerAccessMixin, MatchScopedQuerysetMixin, View):
    """Renders the pending-items breakdown for one match, shown in a popup
    when its teams are clicked on the Missing Operational Requirements
    report - the same items that used to sit in an inline "Details" table."""

    def get(self, request, pk, *args, **kwargs):
        match = get_object_or_404(
            self.filter_matches_queryset(
                Match.objects.select_related("home_club", "away_club", "venue", "competition")
            ),
            pk=pk,
        )
        pending_items = get_missing_requirements_pending_items(match)
        html = render_to_string(
            "operations/partials/missing_requirements_popup.html",
            {"match": match, "pending_items": pending_items},
            request=request,
        )
        return HttpResponse(html)
