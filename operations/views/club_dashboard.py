# operations/views/club_dashboard.py
#
# Club-facing dashboard (Phase 3 of the Club Dashboard feature). Separate
# from the Operations Dashboard on purpose - not a filtered view of it.
#
# Every match shown here is Home OR Away for one of the current user's own
# clubs (get_user_club_ids), never anything the user passes in - there is
# no club_id/match scope taken from GET/POST/hidden fields anywhere below.
# Home vs. Away only changes what's DISPLAYED (a badge + a follow-only
# notice); it never changes what's VISIBLE - both sides of the club's
# fixtures show up in the same list. Actual management capability is
# gated separately, per match, through can_manage_home_match /
# can_upload_home_match_pricing_plan / can_approve_pricing_plan /
# can_publish_match_from_club_dashboard (operations/permissions.py) - this
# page never renders a pricing-plan/SPL/CMS-status control, so those
# functions currently only drive the read-only status text, not any
# button. No new model or migration - every field below already exists on
# Match.

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Max, Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import DetailView, TemplateView

from matches.models import Club, Competition, Match
from operations.forms import ClubPricingPlanUploadForm
from operations.models import ClubPricingPlan, MatchActivityLog
from operations.permissions import (
    can_approve_pricing_plan,
    can_confirm_home_match_submission,
    can_manage_home_match,
    can_publish_match_from_club_dashboard,
    can_submit_home_match_to_spl,
    can_upload_home_match_pricing_plan,
    can_view_club_match,
    can_view_own_club_dashboard,
    get_user_club_ids,
)

from .helpers import build_dashboard_match_state, log_match_activity

CLUB_DASHBOARD_PAGE_SIZE = 20


def _club_owned_matches_queryset(club_ids):
    """The one query every view in this module is built on: Home OR Away
    for one of these specific club ids, nothing else. club_ids always
    comes from get_user_club_ids(request.user) - never from request data -
    so this can't be widened by a query param, a hidden field, or a
    tampered id."""
    return (
        Match.objects.filter(Q(home_club_id__in=club_ids) | Q(away_club_id__in=club_ids))
        .select_related("home_club", "away_club", "venue", "competition")
        .distinct()
    )


def _build_club_match_row(match, club_ids, now):
    """One row's worth of display data: the existing, shared
    build_dashboard_match_state computation (is_live_now, match_finished,
    days_to_match, alert_text, ...) plus which side of this fixture the
    user's club is on, and what they're allowed to do about it."""
    state = build_dashboard_match_state(match, now)
    is_home = match.home_club_id in club_ids
    return {
        **state,
        "is_home": is_home,
        "is_away": not is_home,
    }


class ClubDashboardView(LoginRequiredMixin, TemplateView):
    """The club's own dashboard: summary counts + its full match list
    (Home and Away, every competition), read-only except for the (not yet
    built - Phase 5) pricing-plan/SPL-submission actions on its own Home
    matches. can_view_own_club_dashboard is the single access gate; a user
    with no owned club at all never gets past dispatch()."""

    template_name = "operations/club_dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not can_view_own_club_dashboard(request.user):
            raise PermissionDenied("This dashboard is only available to club accounts.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.localtime()
        today = now.date()

        club_ids = get_user_club_ids(self.request.user)
        clubs = list(Club.objects.filter(id__in=club_ids))

        base_qs = _club_owned_matches_queryset(club_ids)

        # --- Summary counts (all computed from the same club-scoped
        # queryset above - never a separate, looser query). ---
        summary = {
            "upcoming": base_qs.filter(Q(event_date__gte=today) | Q(event_date__isnull=True)).count(),
            "past": base_qs.filter(event_date__lt=today).count(),
            "home_count": base_qs.filter(home_club_id__in=club_ids).count(),
            "away_count": base_qs.filter(away_club_id__in=club_ids).count(),
            "live_count": sum(
                1 for m in base_qs if build_dashboard_match_state(m, now)["is_live_now"]
            ),
        }

        # --- Filterable, paginated match list ---
        matches = base_qs
        selected_type = self.request.GET.get("type", "")  # "home" | "away" | ""
        if selected_type == "home":
            matches = matches.filter(home_club_id__in=club_ids)
        elif selected_type == "away":
            matches = matches.filter(away_club_id__in=club_ids)

        selected_competition = self.request.GET.get("competition", "")
        if selected_competition:
            matches = matches.filter(competition_id=selected_competition)

        selected_status = self.request.GET.get("status", "")
        if selected_status:
            matches = matches.filter(cms_status=selected_status)

        selected_period = self.request.GET.get("period", "")
        if selected_period == "past":
            matches = matches.filter(event_date__lt=today).order_by("-event_date", "-match_start_time", "-id")
        elif selected_period == "upcoming":
            matches = matches.filter(Q(event_date__gte=today) | Q(event_date__isnull=True)).order_by(
                "event_date", "match_start_time", "id"
            )
        else:
            matches = matches.order_by("event_date", "match_start_time", "id")

        paginator = Paginator(matches, CLUB_DASHBOARD_PAGE_SIZE)
        page_obj = paginator.get_page(self.request.GET.get("page", 1))
        rows = [_build_club_match_row(m, club_ids, now) for m in page_obj.object_list]

        competition_ids = base_qs.values_list("competition_id", flat=True).distinct()

        context.update({
            "clubs": clubs,
            "summary": summary,
            "rows": rows,
            "page_obj": page_obj,
            "match_status": Match.Status,
            "status_choices": Match.Status.choices,
            "competitions": Competition.objects.filter(id__in=competition_ids).order_by("sort_order", "name_ar"),
            "selected_type": selected_type,
            "selected_competition": selected_competition,
            "selected_status": selected_status,
            "selected_period": selected_period,
            "today": today,
        })
        return context


class ClubDashboardMatchDetailView(LoginRequiredMixin, DetailView):
    """Read-mostly detail page for one of the club's own matches (Home or
    Away). Deliberately NOT a reuse of the existing MatchDetailView: that
    page assumes full checklist/CMS-status management and is scoped by
    get_visible_matches (Home-only), neither of which fits a page that
    must also show a club's own Away fixtures safely. can_view_club_match
    is the only visibility gate - an id for a match the user's club has no
    part in never resolves, regardless of what's in the URL."""

    model = Match
    template_name = "operations/club_dashboard_match_detail.html"
    context_object_name = "match"

    def get_queryset(self):
        return Match.objects.select_related("home_club", "away_club", "venue", "competition")

    def get_object(self, queryset=None):
        match = super().get_object(queryset)
        if not can_view_club_match(self.request.user, match):
            raise PermissionDenied("You don't have permission to view this match.")
        return match

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        match = self.object
        now = timezone.localtime()
        club_ids = get_user_club_ids(self.request.user)

        context.update({
            "state": build_dashboard_match_state(match, now),
            "is_home": match.home_club_id in club_ids,
            "can_manage_home_match": can_manage_home_match(self.request.user, match),
            "can_upload_pricing_plan": can_upload_home_match_pricing_plan(self.request.user, match),
            "can_submit_to_spl": can_submit_home_match_to_spl(self.request.user, match),
            "can_confirm_submission": can_confirm_home_match_submission(self.request.user, match),
            "can_approve_pricing_plan": can_approve_pricing_plan(self.request.user, match),
            "can_publish_match": can_publish_match_from_club_dashboard(self.request.user, match),
            "recent_activity": match.activity_logs.select_related("user").all()[:8],
            # Only ever shown/used when is_home is True (see the template) -
            # the away club never sees the home club's plan, filename, or a
            # download link for it.
            "current_pricing_plan": match.club_pricing_plans.order_by("-version").first(),
        })
        return context


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
        match = get_object_or_404(Match.objects.select_related("home_club", "away_club"), pk=pk)
        if not can_upload_home_match_pricing_plan(request.user, match):
            raise PermissionDenied("You don't have permission to upload a pricing plan for this match.")
        return match

    def get(self, request, pk, *args, **kwargs):
        match = self._get_match_or_403(request, pk)
        form = ClubPricingPlanUploadForm()
        current_plan = match.club_pricing_plans.order_by("-version").first()
        return self._render(request, match, form, current_plan)

    def post(self, request, pk, *args, **kwargs):
        match = self._get_match_or_403(request, pk)
        form = ClubPricingPlanUploadForm(request.POST, request.FILES)
        if not form.is_valid():
            error_text = " ".join(str(error) for errors in form.errors.values() for error in errors)
            messages.error(request, error_text or _("Could not upload the file."))
            current_plan = match.club_pricing_plans.order_by("-version").first()
            return self._render(request, match, form, current_plan)

        next_version = (
            ClubPricingPlan.objects.filter(match=match).aggregate(Max("version"))["version__max"] or 0
        ) + 1

        plan = form.save(commit=False)
        plan.match = match
        plan.club_id = match.home_club_id
        plan.version = next_version
        plan.status = ClubPricingPlan.Status.UPLOADED
        plan.uploaded_by = request.user
        plan.save()

        log_match_activity(
            match=match,
            action=MatchActivityLog.Action.STATUS_CHANGED,
            description=f"Club pricing plan uploaded (v{plan.version}).",
            user=request.user,
        )
        messages.success(request, _("Pricing plan uploaded. This does not approve it - SPL review still applies."))
        return redirect("operations:club-dashboard-match-detail", pk=match.pk)

    def _render(self, request, match, form, current_plan):
        return render(
            request,
            self.template_name,
            {"match": match, "form": form, "current_plan": current_plan},
        )


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
        return FileResponse(plan.file.open("rb"), as_attachment=True, filename=plan.file.name.rsplit("/", 1)[-1])


def _get_current_plan_or_404(pk):
    """Shared by both Phase 5 views below: the plan must exist AND be its
    match's current (highest) version - an old, already-superseded version
    is never actionable, submitted or not."""
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
