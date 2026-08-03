from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.views import View

from control_panel.permissions import ControlPanelAccessMixin
from matches.models import Match
from operations.permissions import MatchScopedQuerysetMixin


class MatchSlugForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = ["slug"]


class MatchSlugEditView(LoginRequiredMixin, ControlPanelAccessMixin, MatchScopedQuerysetMixin, View):
    def get(self, request, pk, *args, **kwargs):
        match = get_object_or_404(self.filter_matches_queryset(Match.objects.all()), pk=pk)
        form = MatchSlugForm(instance=match)
        html = render_to_string(
            "operations/partials/match_slug_edit_form.html",
            {"match": match, "form": form},
            request=request,
        )
        return HttpResponse(html)


class MatchSlugUpdateView(LoginRequiredMixin, ControlPanelAccessMixin, MatchScopedQuerysetMixin, View):
    def post(self, request, pk, *args, **kwargs):
        match = get_object_or_404(self.filter_matches_queryset(Match.objects.all()), pk=pk)
        form = MatchSlugForm(request.POST, instance=match)

        if form.is_valid():
            form.save()
            html = render_to_string(
                "operations/partials/match_slug_box.html",
                {"match": match, "can_edit_slug": True},
                request=request,
            )
        else:
            html = render_to_string(
                "operations/partials/match_slug_edit_form.html",
                {"match": match, "form": form},
                request=request,
            )
        return HttpResponse(html)
