
from datetime import datetime, time

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.utils import timezone
from django.views.generic import TemplateView

from matches.models import Match
from operations.permissions import ExcludeClubViewerAccessMixin, MatchScopedQuerysetMixin, is_viewer_only

from .helpers import (
    PREP_WINDOW_DAYS,
    build_dashboard_match_state,
    compute_round_stats,
    compute_spl_home_stats,
    get_coordinators_for_matches,
    get_current_round_number,
    get_dashboard_prefetch,
    get_round_date_ranges,
    get_roshan_league_competition,
)


class OperationsDashboardView(LoginRequiredMixin, ExcludeClubViewerAccessMixin, MatchScopedQuerysetMixin, TemplateView):
    template_name = "operations/dashboard.html"
    viewer_template_name = "operations/viewer_dashboard.html"
    TABLE_PAGE_SIZE = 15

    def get(self, request, *args, **kwargs):
        self.viewer_only = is_viewer_only(request.user)
        return super().get(request, *args, **kwargs)

    def get_template_names(self):
        is_round_preview_request = (
            self.request.headers.get("HX-Request") == "true"
            and self.request.headers.get("HX-Target") == "round-preview-panel"
        )
        # Round preview cards are the one piece shared verbatim between the
        # two dashboards - both roles hit this same partial for that swap.
        if is_round_preview_request:
            return ["operations/partials/dashboard_round_preview.html"]

        if self.viewer_only:
            return [self.viewer_template_name]

        # The filter chips (All/Live/Ready/...) swap only the filtered-matches
        # table. The auto-refresh poll (see dashboard.html) targets the whole
        # page and uses hx-select to pull out just its own root div, so it
        # needs the FULL template.
        if self.request.headers.get("HX-Request") == "true":
            target = self.request.headers.get("HX-Target")
            if target == "filtered-matches-panel":
                return ["operations/partials/dashboard_filtered_matches_panel.html"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.viewer_only:
            return self.build_viewer_context(context)
        return self.build_staff_context(context)

    def build_viewer_context(self, context):
        """Simplified, read-mostly dashboard for the Viewer role (the SPL
        monitoring team): scoped to the Roshan League only, with the same
        Teams strip and Rounds strip as the staff dashboard, plus xlsx export
        links (full schedule / by round / by match, all reusing the existing
        SPL Report export)."""
        now = timezone.localtime()
        selected_club = self.request.GET.get("club", "")
        selected_coordinator = self.request.GET.get("coordinator", "")
        selected_spl_approval = self.request.GET.get("spl_approval", "")
        selected_status = self.request.GET.get("status", "")

        roshan_competition = get_roshan_league_competition()

        matches = self.filter_matches_queryset(
            Match.objects.select_related("home_club", "home_club__owner", "away_club", "venue", "competition")
            .prefetch_related(get_dashboard_prefetch())
            .order_by("event_date", "match_start_time")
        )
        if roshan_competition:
            matches = matches.filter(competition=roshan_competition)

        # Defaults to the current matchweek on a fresh page load (no ?round=
        # in the URL at all) so the Rounds strip opens on "what's happening
        # now" instead of an empty round-preview panel - an explicit
        # ?round= (including "" from clearing the filter) is still respected.
        round_date_ranges = get_round_date_ranges(matches)
        current_round_number = get_current_round_number(round_date_ranges, now.date())
        if "round" in self.request.GET:
            selected_round = self.request.GET.get("round", "")
        else:
            selected_round = str(current_round_number) if current_round_number is not None else ""

        match_cards = [build_dashboard_match_state(match, now=now) for match in matches]

        clubs_by_id = {}
        for card in match_cards:
            for club in (card["match"].home_club, card["match"].away_club):
                if club is not None:
                    clubs_by_id[club.pk] = club
        all_clubs = sorted(clubs_by_id.values(), key=lambda c: c.name_ar or c.name_en)

        round_number = None
        if selected_round:
            try:
                round_number = int(selected_round)
            except ValueError:
                round_number = None

        featured_matches = []
        round_stats = None
        if round_number is not None:
            featured_matches = sorted(
                [c for c in match_cards if c["match"].round_number == round_number],
                key=lambda x: (
                    x["match"].event_date or datetime.max.date(),
                    x["match"].match_start_time or time.min,
                ),
            )
            round_stats = compute_round_stats(featured_matches, now.date())
            round_stats["date_range"] = round_date_ranges.get(round_number)

        # Comprehensive Upcoming & Live table - a normal filterable list on
        # top of the team/round browsing above, for "what's coming up and
        # when" at a glance. Finished matches don't belong here by default -
        # note this excludes match_finished, not is_past: a live match's
        # kickoff IS in the past (is_past=True) but it hasn't finished yet,
        # so it must still show up here. Explicitly asking for
        # status=finished (via the League Stats "Finished" card/filter) is
        # the one case that flips this - without this, that filter could
        # never show anything, since every finished match was already
        # dropped before the status check even ran.
        if selected_status == "finished":
            table_cards = [c for c in match_cards if c["match_finished"]]
        else:
            table_cards = [c for c in match_cards if not c["match_finished"]]
        if selected_club:
            table_cards = [c for c in table_cards if str(c["match"].home_club_id) == selected_club]
        if selected_coordinator:
            table_cards = [
                c for c in table_cards
                if c["match"].home_club.owner_id and str(c["match"].home_club.owner_id) == selected_coordinator
            ]
        if round_number is not None:
            table_cards = [c for c in table_cards if c["match"].round_number == round_number]
        if selected_spl_approval == "approved":
            table_cards = [c for c in table_cards if c["match"].ticketing_plan_approved]
        elif selected_spl_approval == "not_approved":
            table_cards = [c for c in table_cards if not c["match"].ticketing_plan_approved]
        if selected_status == "live":
            table_cards = [c for c in table_cards if c["is_live_now"]]
        elif selected_status == "upcoming":
            table_cards = [c for c in table_cards if not c["is_live_now"]]
        elif selected_status == "in_progress":
            table_cards = [c for c in table_cards if c["match"].cms_status == Match.Status.IN_PROGRESS]
        # "finished" needs no further narrowing here - already isolated above.
        table_cards = sorted(
            table_cards,
            key=lambda x: (
                x["days_to_match"] if x["days_to_match"] is not None else 9999,
                x["match"].match_start_time or time.min,
            ),
        )
        table_paginator = Paginator(table_cards, self.TABLE_PAGE_SIZE)
        table_page_obj = table_paginator.get_page(self.request.GET.get("page", 1))

        home_clubs_by_id = {
            club.pk: club for club in all_clubs if club.pk in set(matches.values_list("home_club_id", flat=True))
        }

        # League Stats cards - always over every match, no filter (the old
        # Total/Round/Club "Filter By" form was removed; the per-round
        # numbers now live in the Rounds section's round_stats card instead).
        stats = compute_spl_home_stats(match_cards)

        # Hick's Law: showing all 34 round chips at once is a lot of
        # options to scan for one decision. Default to a small window
        # around whichever round is actually active (falls back to round 1
        # if the league has no current round yet) - "Show all" in the
        # template reveals the rest without a server round-trip.
        window_center = round_number if round_number is not None else (current_round_number or 1)
        round_window = set(range(max(1, window_center - 2), min(34, window_center + 2) + 1))

        context.update({
            "now": now,
            "all_clubs": all_clubs,
            "available_rounds": range(1, 35),
            "round_window": round_window,
            "round_date_ranges": round_date_ranges,
            "current_round_number": current_round_number,
            "selected_round": selected_round,
            "selected_club": selected_club,
            "selected_coordinator": selected_coordinator,
            "selected_spl_approval": selected_spl_approval,
            "selected_status": selected_status,
            "featured_matches": featured_matches,
            "round_stats": round_stats,
            "roshan_competition": roshan_competition,
            "table_clubs": sorted(home_clubs_by_id.values(), key=lambda c: c.name_ar or c.name_en),
            "coordinators": get_coordinators_for_matches(matches),
            "table_cards": table_page_obj.object_list,
            "table_page_obj": table_page_obj,
            "table_match_count": len(table_cards),
            "stats": stats,
        })
        return context

    def build_staff_context(self, context):
        now = timezone.localtime()
        selected_view = self.request.GET.get("view", "all")

        matches = self.filter_matches_queryset(
            Match.objects.select_related("home_club", "away_club", "venue", "sent_to_cms_by")
            .order_by("event_date", "match_start_time")
            .prefetch_related("checklist_items__template_item__category")
        )

        # Scoped to the Roshan League specifically (matching
        # available_rounds = range(1, 35), its 34-round structure) - the
        # Round strip mixes in every other competition's matches too, each
        # with its own independent round numbering, so computing date
        # ranges/"current round" across all of them would be meaningless.
        roshan_competition = get_roshan_league_competition()
        roshan_matches = matches.filter(competition=roshan_competition) if roshan_competition else matches
        round_date_ranges = get_round_date_ranges(roshan_matches)

        # Same "open on the current matchweek by default" rule as the
        # viewer dashboard - see build_viewer_context for why an explicit
        # ?round= (including "") is still respected. Also skipped when
        # ?view= is present without ?round=: that's a filter-chip click
        # (Live/Ready/Alerts/...), which must not get silently overridden
        # by a round default just because the chip's plain <a href> doesn't
        # carry a round param of its own.
        current_round_number = get_current_round_number(round_date_ranges, now.date())
        if "round" in self.request.GET:
            selected_round = self.request.GET.get("round", "")
        elif "view" in self.request.GET:
            selected_round = ""
        else:
            selected_round = str(current_round_number) if current_round_number is not None else ""

        match_cards = [build_dashboard_match_state(match, now=now) for match in matches]

        # Clubs already came in via select_related on `matches`, so this is
        # just deduping in Python instead of a second query.
        clubs_by_id = {}
        for card in match_cards:
            for club in (card["match"].home_club, card["match"].away_club):
                if club is not None:
                    clubs_by_id[club.pk] = club
        all_clubs = sorted(clubs_by_id.values(), key=lambda c: c.name_ar or c.name_en)

        live_matches = [c for c in match_cards if c["is_live_now"]]
        # Bucketing must use is_past (precise kickoff datetime), not
        # days_to_match (calendar-date only) - otherwise a match that already
        # kicked off earlier today still has days_to_match == 0 and lands in
        # "upcoming", so it could wrongly surface as "Ready for Ticket Sale"
        # instead of "Needs Reports" once it's actually over.
        matches_with_date = [c for c in match_cards if c["days_to_match"] is not None]
        upcoming_matches = [c for c in matches_with_date if not c["is_past"]]
        past_matches = [c for c in matches_with_date if c["is_past"]]
        ready_for_ticket_sale_matches = [c for c in upcoming_matches if c["ready_for_ticket_sale"] and not c["is_live_now"]]
        prep_alert_matches = [c for c in upcoming_matches if c["prep_window_started"] and c["non_post_match_pending"] > 0 and not c["is_live_now"]]
        matches_needing_reports = [c for c in past_matches if c["needs_reports"]]
        starting_soon_matches = [c for c in upcoming_matches if c["starting_within_48h"]]

        upcoming_matches = sorted(
            upcoming_matches,
            key=lambda x: (
                x["days_to_match"] if x["days_to_match"] is not None else 9999,
                x["match"].match_start_time or time.min,
            )
        )
        past_matches = sorted(
            past_matches,
            key=lambda x: x["match"].event_date or datetime.min.date(),
            reverse=True,
        )

        # Live matches already have their own dedicated section above this
        # table, so the "all"/"upcoming" table views exclude them to avoid
        # showing the same match twice. The "Live" filter chip still shows
        # every currently-live match via live_matches, untouched.
        non_live_upcoming_matches = [c for c in upcoming_matches if not c["is_live_now"]]

        featured_map = {
            "live": live_matches,
            "ready": ready_for_ticket_sale_matches,
            "alerts": prep_alert_matches,
            "reports": matches_needing_reports,
            "upcoming": non_live_upcoming_matches,
            "past": past_matches,
            "all": non_live_upcoming_matches,
            "starting_soon": starting_soon_matches,
        }
        # Picking a round shows every match in that round regardless of
        # status, overriding the live/ready/alerts/... view chips - it's its
        # own browsing mode ("show me round 12"), not a further narrowing.
        round_number = None
        if selected_round:
            try:
                round_number = int(selected_round)
            except ValueError:
                round_number = None

        round_stats = None
        if round_number is not None:
            featured_matches = sorted(
                [c for c in match_cards if c["match"].round_number == round_number],
                key=lambda x: (
                    x["match"].event_date or datetime.max.date(),
                    x["match"].match_start_time or time.min,
                ),
            )
            round_stats = compute_round_stats(featured_matches, now.date())
            round_stats["date_range"] = round_date_ranges.get(round_number)
        else:
            featured_matches = featured_map.get(selected_view, upcoming_matches)

        stats = {
            "total_matches": len(match_cards),
            "live_matches": len(live_matches),
            "upcoming_matches": len(upcoming_matches),
            "past_matches": len(past_matches),
            "ready_for_ticket_sale_matches": len(ready_for_ticket_sale_matches),
            "prep_alert_matches": len(prep_alert_matches),
            "matches_needing_reports": len(matches_needing_reports),
            "delayed_matches": len([c for c in match_cards if c["delayed_items"] > 0]),
            "starting_soon_matches": len(starting_soon_matches),
        }

        # Hick's Law: showing all 34 round chips at once is a lot of
        # options to scan for one decision - same window-around-the-active-
        # round default as the viewer dashboard (see build_viewer_context).
        window_center = round_number if round_number is not None else (current_round_number or 1)
        round_window = set(range(max(1, window_center - 2), min(34, window_center + 2) + 1))

        context.update({
            "stats": stats,
            "now": now,
            "match_status": Match.Status,
            "prep_window_days": PREP_WINDOW_DAYS,
            "selected_view": selected_view,
            "selected_round": selected_round,
            "available_rounds": range(1, 35),
            "round_window": round_window,
            "round_date_ranges": round_date_ranges,
            "current_round_number": current_round_number,
            "all_clubs": all_clubs,
            # Both shown as compact lists/tables now (pills, table rows), so
            # no need to truncate the way the old card layouts required.
            "live_matches": live_matches,
            "prep_alert_matches": prep_alert_matches,
            "upcoming_matches": upcoming_matches[:12],
            "past_matches": past_matches[:12],
            "featured_matches": featured_matches if round_number is not None else featured_matches[:12],
            "round_stats": round_stats,
        })
        return context
