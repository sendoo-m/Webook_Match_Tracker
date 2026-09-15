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

from datetime import date as date_cls
from datetime import time as time_cls

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView, TemplateView

from matches.models import Club, Competition, Match, Venue, VenueImage, VenueSeatingCategory
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
CLUB_DASHBOARD_UPCOMING_LIMIT = 6

# The club-facing "Match Status" shown on the dashboard's tables is
# deliberately simpler than the internal CMS pipeline (Draft/Ready for
# CMS/Sent to CMS/Published): a coordinator/club viewer only ever needs to
# know whether a match is still being prepared, is live, or already
# happened - see _display_status and club_dashboard_schedule.html's/
# club_dashboard.html's Match Status column.
CLUB_DASHBOARD_STATUS_CHOICES = [
    ("in_progress", _("In Progress")),
    ("live", _("Live")),
    ("finished", _("Finished")),
]


def _display_status(row):
    if row["match_finished"]:
        return "finished"
    if row["is_live_now"]:
        return "live"
    return "in_progress"


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


def _club_home_venue(club_ids):
    """The venue this club's own home matches are played at - there is no
    direct Club -> Venue field (a venue is only ever recorded per-Match),
    so this is derived the same way get_manageable_venue_ids_for_user
    (operations/permissions.py) does it: the venue(s) of the club's own
    HOME fixtures, never an away fixture's venue. Picks the first one -
    a club playing all its home matches at more than one physical venue
    isn't a real scenario in this league."""
    return (
        Venue.objects.filter(matches__home_club_id__in=club_ids, is_active=True)
        .distinct()
        .first()
    )


def _club_total_capacity(club_ids, venue):
    if venue is None:
        return None
    total = (
        VenueSeatingCategory.objects.filter(club_id__in=club_ids, venue=venue, is_active=True)
        .aggregate(total=Sum("seat_count"))["total"]
    )
    return total


def _club_seat_map_image(club_ids, venue):
    """VenueImage isn't scoped to a club (a venue's physical layout is
    shared by every club that plays there) - when two clubs share a venue
    and each uploaded their OWN overview photo of it (e.g. Al Kholood and
    Al Hazm both at Al Hazm Stadium), a plain venue-only lookup would show
    either club's image at random. This club's own seating categories'
    position_image is the only real signal for "which image is actually
    this club's" - same fix as clubs/views/pricing_plan.py's
    _get_venue_images_for_categories, applied here for the homepage
    thumbnail."""
    if venue is None:
        return None
    image_id = (
        VenueSeatingCategory.objects.filter(
            club_id__in=club_ids, venue=venue, is_active=True, position_image__isnull=False,
        )
        .order_by("sort_order")
        .values_list("position_image_id", flat=True)
        .first()
    )
    if image_id is None:
        return None
    return VenueImage.objects.filter(pk=image_id, is_active=True).first()


def _next_round_upcoming_rows(base_qs, club_ids, now):
    """Every not-yet-finished match, starting from the beginning of the
    next round rather than a raw "event_date >= today" cut: a round can
    span several days, and a plain date filter would show only the
    fixtures of the CURRENT round that haven't kicked off yet, silently
    dropping the ones from that same round already played. Matches with
    no round number yet (TBC) are always included, since there's no way
    to know which round they belong to."""
    not_finished = [m for m in base_qs if not build_dashboard_match_state(m, now)["match_finished"]]
    known_rounds = [m.round_number for m in not_finished if m.round_number is not None]
    next_round = min(known_rounds) if known_rounds else None

    if next_round is not None:
        upcoming = [m for m in not_finished if m.round_number is None or m.round_number >= next_round]
    else:
        upcoming = not_finished

    upcoming.sort(
        key=lambda m: (
            m.event_date is None,
            m.event_date or date_cls.max,
            m.match_start_time or time_cls.min,
        )
    )
    return [_build_club_match_row(m, club_ids, now) for m in upcoming[:CLUB_DASHBOARD_UPCOMING_LIMIT]]


class ClubDashboardView(LoginRequiredMixin, TemplateView):
    """The club's own homepage: its identity (logo, name), its home
    venue's seating-map thumbnail and total capacity, and a short look
    at its next round's fixtures. The full, filterable match history/list
    lives on ClubDashboardScheduleView instead - this page is a snapshot,
    not a report. can_view_own_club_dashboard is the single access gate;
    a user with no owned club at all never gets past dispatch()."""

    template_name = "operations/club_dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not can_view_own_club_dashboard(request.user):
            raise PermissionDenied("This dashboard is only available to club accounts.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.localtime()

        club_ids = get_user_club_ids(self.request.user)
        clubs = list(Club.objects.filter(id__in=club_ids))
        primary_club = clubs[0] if clubs else None

        base_qs = _club_owned_matches_queryset(club_ids)
        venue = _club_home_venue(club_ids)

        context.update({
            "clubs": clubs,
            "club": primary_club,
            "venue": venue,
            "total_capacity": _club_total_capacity(club_ids, venue),
            "seat_map_image": _club_seat_map_image(club_ids, venue),
            "upcoming_rows": _next_round_upcoming_rows(base_qs, club_ids, now),
        })
        return context


class ClubDashboardScheduleView(LoginRequiredMixin, TemplateView):
    """The club's full match list (Home and Away, every competition, every
    period), with filters and pagination - reached from the homepage's
    "View all matches" link. Same access gate and club scoping as the
    homepage above; this view only exists to keep the homepage a quick
    snapshot instead of growing back into a full report."""

    template_name = "operations/club_dashboard_schedule.html"

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

        selected_period = self.request.GET.get("period", "")
        if selected_period == "past":
            matches = matches.filter(event_date__lt=today).order_by("-event_date", "-match_start_time", "-id")
        elif selected_period == "upcoming":
            matches = matches.filter(Q(event_date__gte=today) | Q(event_date__isnull=True)).order_by(
                "event_date", "match_start_time", "id"
            )
        else:
            matches = matches.order_by("event_date", "match_start_time", "id")

        # Status is filtered on the same simplified 3-state read the table
        # itself shows (Finished/Live/In Progress - see
        # club_dashboard_schedule.html), not the raw internal CMS pipeline
        # status (Draft/Ready for CMS/Sent to CMS/Published) - a coordinator
        # picking a club-facing status shouldn't need to know that pipeline
        # at all. Computed in Python since it depends on
        # build_dashboard_match_state, not a plain column - fine at this
        # scale (one club's own season, never the whole league).
        rows_all = [_build_club_match_row(m, club_ids, now) for m in matches]
        selected_status = self.request.GET.get("status", "")
        if selected_status:
            rows_all = [row for row in rows_all if _display_status(row) == selected_status]

        paginator = Paginator(rows_all, CLUB_DASHBOARD_PAGE_SIZE)
        page_obj = paginator.get_page(self.request.GET.get("page", 1))
        rows = page_obj.object_list

        competition_ids = base_qs.values_list("competition_id", flat=True).distinct()

        context.update({
            "clubs": clubs,
            "summary": summary,
            "rows": rows,
            "page_obj": page_obj,
            "status_choices": CLUB_DASHBOARD_STATUS_CHOICES,
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
            "recent_activity": match.activity_logs.select_related("user").all()[:3],
            # Only ever shown/used when is_home is True (see the template) -
            # the away club never sees the home club's plan, filename, or a
            # download link for it.
            "current_pricing_plan": match.club_pricing_plans.order_by("-version").first(),
        })
        return context


class ClubDashboardMatchActivityView(LoginRequiredMixin, DetailView):
    """The full activity log for one of the club's own matches - the "view
    all" page the match detail's Recent Activity panel links out to, since
    that panel only shows the latest 3 entries. Same access gate as the
    match detail page itself."""

    model = Match
    template_name = "operations/club_dashboard_match_activity.html"
    context_object_name = "match"

    def get_queryset(self):
        return Match.objects.select_related("home_club", "away_club")

    def get_object(self, queryset=None):
        match = super().get_object(queryset)
        if not can_view_club_match(self.request.user, match):
            raise PermissionDenied("You don't have permission to view this match.")
        return match

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        match = self.object
        logs = match.activity_logs.select_related("user").all()
        paginator = Paginator(logs, CLUB_DASHBOARD_PAGE_SIZE)
        page_obj = paginator.get_page(self.request.GET.get("page", 1))
        context.update({
            "page_obj": page_obj,
            "activity_logs": page_obj.object_list,
        })
        return context
