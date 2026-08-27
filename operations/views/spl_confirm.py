# operations/views/spl_confirm.py

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext as _
from django.views import View

from matches.models import Match
from operations.models import MatchActivityLog
from operations.permissions import MatchScopedQuerysetMixin, can_manage_control_panel, is_viewer_only

from .helpers import log_match_activity


class SPLPlanConfirmView(LoginRequiredMixin, MatchScopedQuerysetMixin, View):
    """Lets the SPL team confirm their own ticketing plan approval for a
    match - the one write action Viewer accounts are allowed, separate from
    the full SPL info edit form (which stays gated behind require_match_access
    for operations staff). One-way: confirms, doesn't un-confirm."""

    def post(self, request, pk, *args, **kwargs):
        if not (is_viewer_only(request.user) or can_manage_control_panel(request.user)):
            raise PermissionDenied("You don't have permission to confirm the SPL ticketing plan.")

        match = get_object_or_404(self.filter_matches_queryset(Match.objects.all()), pk=pk)

        if not match.ticketing_plan_approved:
            match.ticketing_plan_approved = True
            match.save(update_fields=["ticketing_plan_approved", "updated_at"])
            log_match_activity(
                match=match,
                action=MatchActivityLog.Action.STATUS_CHANGED,
                description="SPL ticketing plan confirmed by the SPL team.",
                user=request.user,
            )

        messages.success(request, _("SPL ticketing plan confirmed."))
        referer = request.META.get("HTTP_REFERER")
        return redirect(referer or "operations:spl-report")


class SPLTicketsConfirmView(LoginRequiredMixin, MatchScopedQuerysetMixin, View):
    """Lets the SPL team confirm complimentary tickets were sent for a match
    - same one-way confirm pattern as SPLPlanConfirmView, for spl_tickets_sent
    instead of ticketing_plan_approved."""

    def post(self, request, pk, *args, **kwargs):
        if not (is_viewer_only(request.user) or can_manage_control_panel(request.user)):
            raise PermissionDenied("You don't have permission to confirm SPL complimentary tickets.")

        match = get_object_or_404(self.filter_matches_queryset(Match.objects.all()), pk=pk)

        if not match.spl_tickets_sent:
            match.spl_tickets_sent = True
            match.save(update_fields=["spl_tickets_sent", "updated_at"])
            log_match_activity(
                match=match,
                action=MatchActivityLog.Action.STATUS_CHANGED,
                description="SPL complimentary tickets confirmed by the SPL team.",
                user=request.user,
            )

        messages.success(request, _("SPL complimentary tickets confirmed."))
        referer = request.META.get("HTTP_REFERER")
        return redirect(referer or "operations:spl-report")
