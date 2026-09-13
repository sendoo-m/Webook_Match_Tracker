# spl/views/info.py

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.views import View

from matches.models import Match
from operations.permissions import MatchScopedQuerysetMixin, require_match_access
from operations.views.helpers import build_spl_report_row

from ..forms import MatchSPLInfoForm


class MatchSPLInfoEditView(LoginRequiredMixin, MatchScopedQuerysetMixin, View):
    def get(self, request, pk, *args, **kwargs):
        match = get_object_or_404(self.filter_matches_queryset(Match.objects.all()), pk=pk)
        # Same rule as the discount code: seeing the match is not the same as
        # being allowed to fill in its SPL report fields.
        require_match_access(request.user, match)

        form = MatchSPLInfoForm(instance=match)
        html = render_to_string(
            "operations/partials/match_spl_info_edit_form.html",
            {"match": match, "form": form},
            request=request,
        )
        return HttpResponse(html)


class MatchSPLInfoUpdateView(LoginRequiredMixin, MatchScopedQuerysetMixin, View):
    def post(self, request, pk, *args, **kwargs):
        match = get_object_or_404(self.filter_matches_queryset(Match.objects.all()), pk=pk)
        require_match_access(request.user, match)

        form = MatchSPLInfoForm(request.POST, instance=match)

        if form.is_valid():
            form.save()
            html = render_to_string(
                "operations/partials/match_spl_info_box.html",
                {"match": match, "can_edit": True, **build_spl_report_row(match, timezone.localtime())},
                request=request,
            )
        else:
            html = render_to_string(
                "operations/partials/match_spl_info_edit_form.html",
                {"match": match, "form": form},
                request=request,
            )
        return HttpResponse(html)
