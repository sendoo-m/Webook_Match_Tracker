# operations/views/discount.py

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.views import View

from matches.models import Match
from operations.forms import MatchDiscountForm
from operations.permissions import MatchScopedQuerysetMixin, require_match_access


class MatchDiscountEditView(LoginRequiredMixin, MatchScopedQuerysetMixin, View):
    def get(self, request, pk, *args, **kwargs):
        match = get_object_or_404(self.filter_matches_queryset(Match.objects.all()), pk=pk)
        # Being able to SEE the match is not the same as being allowed to set
        # its discount code — that's reserved for the owning Club Manager (or
        # Super Admin), same as checklist/CMS edits.
        require_match_access(request.user, match)

        form = MatchDiscountForm(instance=match)
        html = render_to_string(
            "operations/partials/match_discount_edit_form.html",
            {"match": match, "form": form},
            request=request,
        )
        return HttpResponse(html)


class MatchDiscountUpdateView(LoginRequiredMixin, MatchScopedQuerysetMixin, View):
    def post(self, request, pk, *args, **kwargs):
        match = get_object_or_404(self.filter_matches_queryset(Match.objects.all()), pk=pk)
        require_match_access(request.user, match)

        form = MatchDiscountForm(request.POST, instance=match)

        if form.is_valid():
            form.save()
            html = render_to_string(
                "operations/partials/match_discount_box.html",
                {"match": match, "can_edit": True},
                request=request,
            )
        else:
            html = render_to_string(
                "operations/partials/match_discount_edit_form.html",
                {"match": match, "form": form},
                request=request,
            )
        return HttpResponse(html)
