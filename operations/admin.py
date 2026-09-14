from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.db import transaction
from django.shortcuts import render
from django.utils import timezone

from notifications.services import notify_club
from operations.views.helpers import log_match_activity

from .models import ClubPricingPlan, ClubPricingPlanCategoryPrice, MatchActivityLog

# Local to this decision flow - mirrors spl/views/pricing_plan_decision.py's
# own constants (not registered on notifications.Notification.NotificationType
# since notification_type is a plain CharField).
NOTIFICATION_TYPE_PLAN_APPROVED = "pricing_plan_approved"
NOTIFICATION_TYPE_PLAN_REJECTED = "pricing_plan_rejected"


@admin.register(MatchActivityLog)
class MatchActivityLogAdmin(admin.ModelAdmin):
    list_display = ("match", "action", "user", "created_at")
    list_filter = ("action", "created_at")
    search_fields = (
        "match__title_en",
        "match__title_ar",
        "user__username",
        "user__email",
        "description",
    )
    autocomplete_fields = ("match", "user")
    ordering = ("-created_at", "-id")


class ClubPricingPlanCategoryPriceInline(admin.TabularInline):
    """The structured per-category prices behind a plan's seat-map/pricing
    table (matches.VenueSeatingCategory codes) - the same data shown on the
    club-facing pricing-plan page and in the Control Panel's seat map."""

    model = ClubPricingPlanCategoryPrice
    extra = 0
    autocomplete_fields = ("category",)


def _current_plan_or_none(plan):
    current = plan.match.club_pricing_plans.order_by("-version").first()
    return current if current is not None and current.pk == plan.pk else None


class RejectPricingPlanForm(forms.Form):
    note = forms.CharField(
        label="Reason (required)",
        widget=forms.Textarea,
        help_text="Explains what the club needs to change - shown to them and required to reject.",
    )


@admin.register(ClubPricingPlan)
class ClubPricingPlanAdmin(admin.ModelAdmin):
    """SPL's approve/reject decision on a club's pricing plan - the same
    business logic as spl/views/pricing_plan_decision.py's two views
    (Control Panel's "SPL Approvals" screen), triggered from here instead
    via the two actions below. Approving/rejecting only ever acts on a
    plan's CURRENT version and only while its decision is still PENDING -
    an already-decided or superseded plan is skipped with a message rather
    than silently re-decided."""

    list_display = ("match", "club", "version", "status", "spl_decision", "uploaded_by", "uploaded_at")
    list_filter = ("status", "spl_decision", "uploaded_at")
    search_fields = ("match__title_en", "match__title_ar", "club__name_en", "club__name_ar")
    autocomplete_fields = ("match", "club", "uploaded_by", "submitted_by", "confirmed_by", "spl_decision_by")
    readonly_fields = ("spl_decision_at", "spl_decision_by", "seat_map_snapshot", "updated_at")
    inlines = [ClubPricingPlanCategoryPriceInline]
    actions = ["approve_pricing_plans", "reject_pricing_plans"]
    ordering = ("-uploaded_at",)

    @admin.action(description="Approve selected pricing plans")
    def approve_pricing_plans(self, request, queryset):
        approved = 0
        skipped = 0
        for plan in queryset.select_related("match", "match__home_club", "club"):
            with transaction.atomic():
                plan = ClubPricingPlan.objects.select_for_update().select_related("match").get(pk=plan.pk)
                if _current_plan_or_none(plan) is None or plan.spl_decision != ClubPricingPlan.SPLDecision.PENDING:
                    skipped += 1
                    continue

                plan.spl_decision = ClubPricingPlan.SPLDecision.APPROVED
                plan.spl_decision_at = timezone.now()
                plan.spl_decision_by = request.user
                plan.save(update_fields=["spl_decision", "spl_decision_at", "spl_decision_by", "updated_at"])
                plan.generate_seat_map_snapshot()

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
                notify_club(
                    match,
                    NOTIFICATION_TYPE_PLAN_APPROVED,
                    f"SPL approved the pricing plan (v{plan.version}) for {match}.",
                    plan=plan,
                )
                approved += 1

        if approved:
            messages.success(request, f"Approved {approved} pricing plan(s). The club has been notified.")
        if skipped:
            messages.warning(request, f"Skipped {skipped} plan(s) - not the current version or already decided.")

    @admin.action(description="Reject selected pricing plans (asks for a reason)")
    def reject_pricing_plans(self, request, queryset):
        if "apply" in request.POST:
            form = RejectPricingPlanForm(request.POST)
            if form.is_valid():
                note = form.cleaned_data["note"]
                rejected = 0
                skipped = 0
                for plan in queryset.select_related("match", "match__home_club", "club"):
                    with transaction.atomic():
                        plan = ClubPricingPlan.objects.select_for_update().select_related("match").get(pk=plan.pk)
                        if (
                            _current_plan_or_none(plan) is None
                            or plan.spl_decision != ClubPricingPlan.SPLDecision.PENDING
                        ):
                            skipped += 1
                            continue

                        plan.spl_decision = ClubPricingPlan.SPLDecision.REJECTED
                        plan.spl_decision_at = timezone.now()
                        plan.spl_decision_by = request.user
                        plan.spl_decision_note = note
                        plan.save(update_fields=[
                            "spl_decision", "spl_decision_at", "spl_decision_by", "spl_decision_note", "updated_at",
                        ])
                        plan.generate_seat_map_snapshot()

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
                        notify_club(
                            match,
                            NOTIFICATION_TYPE_PLAN_REJECTED,
                            f"SPL rejected the pricing plan (v{plan.version}) for {match}. Reason: {note}",
                            plan=plan,
                        )
                        rejected += 1

                if rejected:
                    messages.success(request, f"Rejected {rejected} pricing plan(s). The club has been notified.")
                if skipped:
                    messages.warning(request, f"Skipped {skipped} plan(s) - not the current version or already decided.")
                return None
        else:
            form = RejectPricingPlanForm()

        return render(
            request,
            "admin/operations/reject_pricing_plans.html",
            {
                "plans": queryset,
                "form": form,
                "action_checkbox_name": ACTION_CHECKBOX_NAME,
                "title": "Reject pricing plans",
            },
        )
