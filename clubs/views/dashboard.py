# clubs/views/dashboard.py
#
# Club-facing dashboard. Separate from the Operations Dashboard on purpose -
# not a filtered view of it.
#
# Every match shown here is Home OR Away for one of the current user's own
# clubs (get_user_club_ids), never anything the user passes in - there is
# no club_id/match scope taken from GET/POST/hidden fields anywhere below.
# Home vs. Away only changes what's DISPLAYED (a badge + a follow-only
# notice); it never changes what's VISIBLE - both sides of the club's
# fixtures show up in the same list. Actual management capability is
# gated separately, per match, through can_manage_home_match /
# can_upload_home_match_pricing_plan / can_approve_pricing_plan /
# can_publish_match_from_club_dashboard (operations/permissions.py - kept
# there since user_can_manage_match, the core football permission check,
# depends on can_manage_home_match internally) - this page never renders a
# pricing-plan/SPL/CMS-status control, so those functions currently only
# drive the read-only status text, not any button.
#
# ClubPricingPlan itself is defined in operations/models.py, not here - see
# clubs/forms.py for why.

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from django.views.generic import DetailView, TemplateView

from matches.models import Club, Competition, Match
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
from operations.views.helpers import build_dashboard_match_state

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
    (Home and Away, every competition), read-only except for the pricing-
    plan/SPL-submission actions on its own Home matches.
    can_view_own_club_dashboard is the single access gate; a user with no
    owned club at all never gets past dispatch()."""

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
