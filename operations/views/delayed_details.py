# operations/views/delayed_details.py

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.views import View

from checklists.models import MatchChecklistItem
from matches.models import Match
from operations.permissions import MatchScopedQuerysetMixin


class MatchDelayedDetailsView(LoginRequiredMixin, MatchScopedQuerysetMixin, View):
    """Renders the delayed checklist items for one match, for the dashboard's
    "click the delayed count" panel that appears above the filtered table."""

    def get(self, request, pk, *args, **kwargs):
        match = get_object_or_404(
            self.filter_matches_queryset(Match.objects.select_related("home_club", "away_club")),
            pk=pk,
        )
        delayed_items = match.checklist_items.select_related("template_item__category").filter(
            is_active=True,
            status=MatchChecklistItem.Status.DELAYED,
        ).order_by("template_item__category__sort_order", "template_item__sort_order")

        html = render_to_string(
            "operations/partials/dashboard_delayed_details.html",
            {"match": match, "delayed_items": delayed_items},
            request=request,
        )
        return HttpResponse(html)
