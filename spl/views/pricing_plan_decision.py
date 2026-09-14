# spl/views/pricing_plan_decision.py
#
# SPL's approve/reject decision on a club's ClubPricingPlan submission -
# the piece that was missing entirely before: SPLApprovalsView only ever
# read/wrote Match.ticketing_plan_approved (a plain boolean with no reject
# path), with no visibility into the club's own versioned plan at all.
# These two actions act on a ClubPricingPlan directly and keep
# Match.ticketing_plan_approved in sync so every existing boolean-consuming
# page keeps working unchanged (see ClubPricingPlan.spl_decision's own
# comment in operations/models.py).

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views import View

from operations.models import ClubPricingPlan, MatchActivityLog
from operations.permissions import can_approve_pricing_plan
from operations.views.helpers import log_match_activity


def _get_current_plan_or_403(pk):
    plan = get_object_or_404(ClubPricingPlan.objects.select_related("match", "club"), pk=pk)
    current = plan.match.club_pricing_plans.order_by("-version").first()
    if current is None or current.pk != plan.pk:
        raise PermissionDenied("Only the current pricing plan version can be decided on.")
    return plan


class SPLPricingPlanApproveView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        plan = _get_current_plan_or_403(pk)
        if not can_approve_pricing_plan(request.user, plan.match):
            raise PermissionDenied("You don't have permission to approve this pricing plan.")

        plan.spl_decision = ClubPricingPlan.SPLDecision.APPROVED
        plan.spl_decision_at = timezone.now()
        plan.spl_decision_by = request.user
        plan.save(update_fields=["spl_decision", "spl_decision_at", "spl_decision_by", "updated_at"])

        match = plan.match
        match.ticketing_plan_approved = True
        match.ticketing_plan_approved_at = timezone.now()
        match.save(update_fields=["ticketing_plan_approved", "ticketing_plan_approved_at", "updated_at"])

        log_match_activity(
            match=match,
            action=MatchActivityLog.Action.STATUS_CHANGED,
            description=f"SPL approved pricing plan v{plan.version}.",
            user=request.user,
        )
        messages.success(request, _("Pricing plan approved."))
        referer = request.META.get("HTTP_REFERER")
        return redirect(referer or "operations:spl-approvals")


class SPLPricingPlanRejectView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        plan = _get_current_plan_or_403(pk)
        if not can_approve_pricing_plan(request.user, plan.match):
            raise PermissionDenied("You don't have permission to reject this pricing plan.")

        note = request.POST.get("note", "").strip()
        if not note:
            messages.error(request, _("A note explaining what needs to change is required to reject a pricing plan."))
            referer = request.META.get("HTTP_REFERER")
            return redirect(referer or "operations:spl-approvals")

        plan.spl_decision = ClubPricingPlan.SPLDecision.REJECTED
        plan.spl_decision_at = timezone.now()
        plan.spl_decision_by = request.user
        plan.spl_decision_note = note
        plan.save(update_fields=[
            "spl_decision", "spl_decision_at", "spl_decision_by", "spl_decision_note", "updated_at",
        ])

        match = plan.match
        match.ticketing_plan_approved = False
        match.ticketing_plan_approved_at = None
        match.save(update_fields=["ticketing_plan_approved", "ticketing_plan_approved_at", "updated_at"])

        log_match_activity(
            match=match,
            action=MatchActivityLog.Action.STATUS_CHANGED,
            description=f"SPL rejected pricing plan v{plan.version}: {note}",
            user=request.user,
        )
        messages.success(request, _("Pricing plan rejected. The club can now upload a corrected version."))
        referer = request.META.get("HTTP_REFERER")
        return redirect(referer or "operations:spl-approvals")
