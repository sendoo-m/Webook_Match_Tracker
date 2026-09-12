# operations/views/spl_confirm.py

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views import View

from matches.models import Match
from operations.forms import SPLPlanApprovalUploadForm
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
            match.ticketing_plan_approved_at = timezone.now()
            match.save(update_fields=["ticketing_plan_approved", "ticketing_plan_approved_at", "updated_at"])
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
            match.spl_tickets_sent_at = timezone.now()
            match.save(update_fields=["spl_tickets_sent", "spl_tickets_sent_at", "updated_at"])
            log_match_activity(
                match=match,
                action=MatchActivityLog.Action.STATUS_CHANGED,
                description="SPL complimentary tickets confirmed by the SPL team.",
                user=request.user,
            )

        messages.success(request, _("SPL complimentary tickets confirmed."))
        referer = request.META.get("HTTP_REFERER")
        return redirect(referer or "operations:spl-report")


class SPLPlanApprovalUploadView(LoginRequiredMixin, MatchScopedQuerysetMixin, View):
    """Lets the SPL team attach the signed ticketing plan approval document
    (image or office file) to a match - same permission gate as
    SPLPlanConfirmView, storing a file instead of flipping a boolean."""

    def post(self, request, pk, *args, **kwargs):
        if not (is_viewer_only(request.user) or can_manage_control_panel(request.user)):
            raise PermissionDenied("You don't have permission to upload the SPL plan approval file.")

        match = get_object_or_404(self.filter_matches_queryset(Match.objects.all()), pk=pk)
        form = SPLPlanApprovalUploadForm(request.POST, request.FILES, instance=match)

        if form.is_valid():
            form.save()
            match.plan_approval_file_uploaded_at = timezone.now()
            match.save(update_fields=["plan_approval_file_uploaded_at"])
            log_match_activity(
                match=match,
                action=MatchActivityLog.Action.STATUS_CHANGED,
                description="SPL ticketing plan approval file uploaded.",
                user=request.user,
            )
            messages.success(request, _("Plan approval file uploaded."))
        else:
            error_text = " ".join(str(error) for errors in form.errors.values() for error in errors)
            messages.error(request, error_text or _("Could not upload the file."))

        referer = request.META.get("HTTP_REFERER")
        return redirect(referer or "operations:spl-report")
