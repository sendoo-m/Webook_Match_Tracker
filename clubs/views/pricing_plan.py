# clubs/views/pricing_plan.py
#
# ClubPricingPlan itself is defined in operations/models.py, not here - see
# clubs/forms.py for why. These views are the only place its rows are
# created or advanced through UPLOADED -> SUBMITTED_TO_SPL ->
# SUBMISSION_CONFIRMED.

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Max
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views import View

from matches.models import MapPlacement, Match, VenueImage, VenueSeatingCategory
from operations.models import ClubPricingPlan, ClubPricingPlanCategoryPrice, MatchActivityLog
from operations.permissions import (
    can_confirm_home_match_submission,
    can_manage_home_match,
    can_submit_home_match_to_spl,
    can_upload_home_match_pricing_plan,
)
from operations.views.helpers import log_match_activity

from notifications.models import Notification
from notifications.services import notify_spl

from ..forms import ClubPricingPlanCategoryImportForm, ClubPricingPlanUploadForm
from ..pricing_import_export import build_plan_category_price_template_xlsx, parse_plan_category_prices_xlsx


def _get_categories_for_match(match):
    if not match.venue_id:
        return VenueSeatingCategory.objects.none()
    return VenueSeatingCategory.objects.filter(
        venue_id=match.venue_id, club_id=match.home_club_id, is_active=True
    ).order_by("sort_order", "code")


def _get_venue_images_for_categories(categories):
    """VenueImage itself isn't scoped to a club (a venue's physical layout
    is shared by every club that plays there) - but when two clubs share
    a venue and each uploaded their OWN overview photo of it (e.g. Al
    Kholood and Al Hazm both at Al Hazm Stadium), this club's own
    categories' MapPlacement is the only real signal for "which of the
    venue's images is actually this club's". Filtering by it here means
    the upload page only ever shows the image(s) this club's own
    categories are positioned on, never another club's - at the cost of
    showing nothing yet if this club's categories haven't been
    positioned in the Control Panel."""
    image_ids = MapPlacement.objects.filter(
        category__in=categories, is_active=True
    ).values_list("position_image_id", flat=True).distinct()
    return VenueImage.objects.filter(id__in=image_ids, is_active=True).order_by("sort_order")


class ClubPricingPlanUploadView(LoginRequiredMixin, View):
    """Lets the home club upload (or replace, as a new version - see
    ClubPricingPlan's docstring) its own pricing-plan document for one of
    its own home matches. can_upload_home_match_pricing_plan is the single
    gate: it already requires can_manage_home_match (home club + granted
    competition) plus a state check (not yet SPL-approved, not yet
    Sent-to-CMS/Published) before this view does anything. match/club/
    version/uploaded_by are all computed here from the match and the
    logged-in user - the form only ever carries the file itself."""

    template_name = "operations/club_pricing_plan_upload.html"

    def _get_match_or_403(self, request, pk):
        match = get_object_or_404(Match.objects.select_related("home_club", "away_club", "venue"), pk=pk)
        if not can_upload_home_match_pricing_plan(request.user, match):
            raise PermissionDenied("You don't have permission to upload a pricing plan for this match.")
        return match

    def get(self, request, pk, *args, **kwargs):
        match = self._get_match_or_403(request, pk)
        categories = _get_categories_for_match(match)
        form = ClubPricingPlanUploadForm(categories=categories)
        import_form = ClubPricingPlanCategoryImportForm()
        current_plan = match.club_pricing_plans.order_by("-version").first()
        return self._render(request, match, form, import_form, current_plan, categories)

    def post(self, request, pk, *args, **kwargs):
        match = self._get_match_or_403(request, pk)
        categories = _get_categories_for_match(match)
        form = ClubPricingPlanUploadForm(request.POST, request.FILES, categories=categories)
        import_form = ClubPricingPlanCategoryImportForm()
        current_plan = match.club_pricing_plans.order_by("-version").first()

        if not form.is_valid():
            error_text = " ".join(str(error) for errors in form.errors.values() for error in errors)
            messages.error(request, error_text or _("Could not save the pricing plan."))
            return self._render(request, match, form, import_form, current_plan, categories)

        if not form.has_any_pricing_input():
            messages.error(request, _("Enter at least one category price or attach a file before saving."))
            return self._render(request, match, form, import_form, current_plan, categories)

        next_version = (
            ClubPricingPlan.objects.filter(match=match).aggregate(Max("version"))["version__max"] or 0
        ) + 1

        with transaction.atomic():
            plan = form.save(commit=False)
            plan.match = match
            plan.club_id = match.home_club_id
            plan.version = next_version
            plan.status = ClubPricingPlan.Status.UPLOADED
            plan.uploaded_by = request.user
            plan.save()

            entered_prices = form.get_entered_prices()
            if entered_prices:
                ClubPricingPlanCategoryPrice.objects.bulk_create(
                    ClubPricingPlanCategoryPrice(plan=plan, category_id=category_id, price=price)
                    for category_id, price in entered_prices.items()
                )

        log_match_activity(
            match=match,
            action=MatchActivityLog.Action.STATUS_CHANGED,
            description=f"Club pricing plan uploaded (v{plan.version}).",
            user=request.user,
        )
        notify_spl(
            Notification.NotificationType.PRICING_PLAN_UPLOADED,
            f"{match.home_club} uploaded a pricing plan (v{plan.version}) for {match}.",
            match=match,
            plan=plan,
        )
        messages.success(request, _("Pricing plan uploaded. This does not approve it - SPL review still applies."))
        return redirect("operations:club-dashboard-match-detail", pk=match.pk)

    def _render(self, request, match, form, import_form, current_plan, categories):
        return render(
            request,
            self.template_name,
            {
                "match": match,
                "form": form,
                "import_form": import_form,
                "current_plan": current_plan,
                "categories": categories,
                "venue_images": _get_venue_images_for_categories(categories),
            },
        )


class ClubPricingPlanCategoryTemplateView(LoginRequiredMixin, View):
    """Downloads a ready-to-fill spreadsheet for this match's own venue/
    club seating categories (code pre-filled, price left blank) - so a
    club can just fill in the price column and re-upload it via the
    "Or Upload an Excel File" import below, instead of typing category
    codes by hand. Same access gate as the upload page itself."""

    def get(self, request, pk, *args, **kwargs):
        match = get_object_or_404(Match.objects.select_related("home_club"), pk=pk)
        if not can_upload_home_match_pricing_plan(request.user, match):
            raise PermissionDenied("You don't have permission to upload a pricing plan for this match.")

        categories = _get_categories_for_match(match)
        content = build_plan_category_price_template_xlsx(categories)
        response = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="pricing_template_match_{match.pk}.xlsx"'
        return response


class ClubPricingPlanCategoryImportView(LoginRequiredMixin, View):
    """The Excel-upload alternative to typing prices in one by one on the
    same page - parses the whole file first and only creates a new
    ClubPricingPlan version if every row resolves cleanly, so a bad file
    never creates a partially-priced version."""

    def post(self, request, pk, *args, **kwargs):
        match = get_object_or_404(Match.objects.select_related("home_club", "away_club", "venue"), pk=pk)
        if not can_upload_home_match_pricing_plan(request.user, match):
            raise PermissionDenied("You don't have permission to upload a pricing plan for this match.")

        form = ClubPricingPlanCategoryImportForm(request.POST, request.FILES)
        if not form.is_valid():
            error_text = " ".join(str(error) for errors in form.errors.values() for error in errors)
            messages.error(request, error_text or _("Could not read the file."))
            return redirect("operations:club-pricing-plan-upload", pk=match.pk)

        if not match.venue_id:
            messages.error(request, _("This match has no venue set, so it has no seating categories to price against."))
            return redirect("operations:club-pricing-plan-upload", pk=match.pk)

        prices_by_category_id, result = parse_plan_category_prices_xlsx(
            form.cleaned_data["import_file"], match.venue, match.home_club
        )

        if result.errors or not prices_by_category_id:
            for row_number, message in result.errors:
                messages.error(request, f"Row {row_number}: {message}")
            if not result.errors:
                messages.error(request, _("No valid category prices found in the file."))
            return redirect("operations:club-pricing-plan-upload", pk=match.pk)

        next_version = (
            ClubPricingPlan.objects.filter(match=match).aggregate(Max("version"))["version__max"] or 0
        ) + 1

        with transaction.atomic():
            plan = ClubPricingPlan.objects.create(
                match=match,
                club_id=match.home_club_id,
                version=next_version,
                status=ClubPricingPlan.Status.UPLOADED,
                uploaded_by=request.user,
                home_percentage=form.cleaned_data["home_percentage"],
            )
            ClubPricingPlanCategoryPrice.objects.bulk_create(
                ClubPricingPlanCategoryPrice(plan=plan, category_id=category_id, price=price)
                for category_id, price in prices_by_category_id.items()
            )

        log_match_activity(
            match=match,
            action=MatchActivityLog.Action.STATUS_CHANGED,
            description=f"Club pricing plan uploaded via Excel import (v{plan.version}, {len(prices_by_category_id)} categories).",
            user=request.user,
        )
        notify_spl(
            Notification.NotificationType.PRICING_PLAN_UPLOADED,
            f"{match.home_club} uploaded a pricing plan (v{plan.version}) for {match}.",
            match=match,
            plan=plan,
        )
        messages.success(
            request,
            _("Pricing plan imported (%(count)s categories). This does not approve it - SPL review still applies.")
            % {"count": len(prices_by_category_id)},
        )
        return redirect("operations:club-dashboard-match-detail", pk=match.pk)


class ClubPricingPlanDownloadView(LoginRequiredMixin, View):
    """The only way to read a ClubPricingPlan's file - never a direct
    /media/ URL. Deliberately stricter than can_view_club_match: only the
    home club that owns this plan (can_manage_home_match) can download it,
    so an away club can never fetch the host club's pricing-plan file by
    guessing or copying a plan id, even though it CAN see the match
    itself."""

    def get(self, request, pk, *args, **kwargs):
        plan = get_object_or_404(ClubPricingPlan.objects.select_related("match", "club"), pk=pk)
        if not can_manage_home_match(request.user, plan.match):
            raise PermissionDenied("You don't have permission to download this file.")
        if not plan.file:
            raise Http404("This pricing plan version has no attached file (it was entered as category prices).")
        return FileResponse(plan.file.open("rb"), as_attachment=True, filename=plan.file.name.rsplit("/", 1)[-1])


def _get_current_plan_or_404(pk):
    """Shared by both views below: the plan must exist AND be its match's
    current (highest) version - an old, already-superseded version is
    never actionable, submitted or not."""
    plan = get_object_or_404(
        ClubPricingPlan.objects.select_related("match", "match__home_club", "match__away_club", "match__competition", "club"),
        pk=pk,
    )
    current = plan.match.club_pricing_plans.order_by("-version").first()
    if current is None or current.pk != plan.pk:
        raise PermissionDenied("Only the current pricing plan version can be acted on.")
    return plan


class ClubPricingPlanSubmitView(LoginRequiredMixin, View):
    """Home club sends its current, uploaded pricing plan to SPL - a
    one-way move from UPLOADED to SUBMITTED_TO_SPL. Distinct from and
    unrelated to Match.ticketing_plan_approved (SPL's own decision,
    untouched here), Match.cms_status, and Match.spl_tickets_sent (SPL's
    complimentary tickets, a different concept entirely). Does not publish
    the match and does not approve anything - it only records that the
    club sent its plan."""

    template_name = "operations/club_pricing_plan_submit.html"

    def get(self, request, pk, *args, **kwargs):
        plan = _get_current_plan_or_404(pk)
        if not can_submit_home_match_to_spl(request.user, plan.match):
            raise PermissionDenied("You don't have permission to submit this pricing plan to SPL.")
        return render(request, self.template_name, {"plan": plan, "match": plan.match})

    def post(self, request, pk, *args, **kwargs):
        with transaction.atomic():
            plan = ClubPricingPlan.objects.select_for_update().select_related("match").get(pk=pk)
            current = plan.match.club_pricing_plans.order_by("-version").first()
            if current is None or current.pk != plan.pk:
                raise PermissionDenied("Only the current pricing plan version can be acted on.")
            if not can_submit_home_match_to_spl(request.user, plan.match):
                raise PermissionDenied("You don't have permission to submit this pricing plan to SPL.")

            if plan.status != ClubPricingPlan.Status.UPLOADED:
                # Already submitted (a double-click, or a stale page) -
                # nothing to redo, no duplicate log entry.
                messages.error(request, _("This pricing plan has already been submitted to SPL."))
                return redirect("operations:club-dashboard-match-detail", pk=plan.match_id)

            plan.status = ClubPricingPlan.Status.SUBMITTED_TO_SPL
            plan.submitted_at = timezone.now()
            plan.submitted_by = request.user
            plan.save(update_fields=["status", "submitted_at", "submitted_by", "updated_at"])

            log_match_activity(
                match=plan.match,
                action=MatchActivityLog.Action.STATUS_CHANGED,
                description=f"Club submitted pricing plan v{plan.version} to SPL.",
                user=request.user,
            )

        messages.success(
            request,
            _("Pricing plan submitted to SPL. This is not an SPL approval and does not publish the match."),
        )
        return redirect("operations:club-dashboard-match-detail", pk=plan.match_id)


class ClubPricingPlanConfirmSubmissionView(LoginRequiredMixin, View):
    """Home club confirms its already-submitted plan - a one-way move from
    SUBMITTED_TO_SPL to SUBMISSION_CONFIRMED. Still not an SPL decision and
    still doesn't publish the match; once confirmed, there is no way back
    (no "undo" action exists for this state)."""

    template_name = "operations/club_pricing_plan_confirm_submission.html"

    def get(self, request, pk, *args, **kwargs):
        plan = _get_current_plan_or_404(pk)
        if not can_confirm_home_match_submission(request.user, plan.match):
            raise PermissionDenied("You don't have permission to confirm this pricing plan submission.")
        return render(request, self.template_name, {"plan": plan, "match": plan.match})

    def post(self, request, pk, *args, **kwargs):
        with transaction.atomic():
            plan = ClubPricingPlan.objects.select_for_update().select_related("match").get(pk=pk)
            current = plan.match.club_pricing_plans.order_by("-version").first()
            if current is None or current.pk != plan.pk:
                raise PermissionDenied("Only the current pricing plan version can be acted on.")
            if not can_confirm_home_match_submission(request.user, plan.match):
                raise PermissionDenied("You don't have permission to confirm this pricing plan submission.")

            if plan.status != ClubPricingPlan.Status.SUBMITTED_TO_SPL:
                messages.error(request, _("This pricing plan submission has already been confirmed, or was never submitted."))
                return redirect("operations:club-dashboard-match-detail", pk=plan.match_id)

            old_status = plan.status
            plan.status = ClubPricingPlan.Status.SUBMISSION_CONFIRMED
            plan.confirmed_at = timezone.now()
            plan.confirmed_by = request.user
            plan.save(update_fields=["status", "confirmed_at", "confirmed_by", "updated_at"])

            log_match_activity(
                match=plan.match,
                action=MatchActivityLog.Action.STATUS_CHANGED,
                description=(
                    f"Club confirmed pricing plan v{plan.version} submission to SPL "
                    f"({old_status} → {plan.status})."
                ),
                user=request.user,
            )

        messages.success(request, _("Pricing plan submission confirmed."))
        return redirect("operations:club-dashboard-match-detail", pk=plan.match_id)
