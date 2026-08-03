
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.views import View

from matches.models import Match
from operations.permissions import MatchScopedQuerysetMixin

from .helpers import get_match_activity_page_context

class MatchActivityLogListView(LoginRequiredMixin, MatchScopedQuerysetMixin, View):
    def get(self, request, pk, *args, **kwargs):
        match = get_object_or_404(
            self.filter_matches_queryset(Match.objects.all()),
            pk=pk,
        )
        page_number = request.GET.get("page", 1)
        context = get_match_activity_page_context(match, page=page_number)
        return HttpResponse(
            render_to_string("operations/partials/activity_log_page.html", context, request=request)
        )
