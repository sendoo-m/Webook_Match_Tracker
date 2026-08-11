
from datetime import datetime, time

from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.views.generic import TemplateView

from matches.models import Match
from operations.permissions import MatchScopedQuerysetMixin

from .helpers import PREP_WINDOW_DAYS, build_dashboard_match_state


class OperationsDashboardView(LoginRequiredMixin, MatchScopedQuerysetMixin, TemplateView):
    template_name = "operations/dashboard.html"

    def get_template_names(self):
        # The filter chips (All/Live/Ready/...) swap only the filtered-matches
        # table. The auto-refresh poll (see dashboard.html) targets the whole
        # page instead and uses hx-select to pull out just its own root div,
        # so it needs the FULL template rendered, not this partial.
        if (
            self.request.headers.get("HX-Request") == "true"
            and self.request.headers.get("HX-Target") == "filtered-matches-panel"
        ):
            return ["operations/partials/dashboard_filtered_matches_panel.html"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.localtime()
        selected_view = self.request.GET.get("view", "all")

        matches = self.filter_matches_queryset(
            Match.objects.select_related("home_club", "away_club", "venue", "sent_to_cms_by")
            .order_by("event_date", "match_start_time")
            .prefetch_related("checklist_items__template_item__category")
        )
        match_cards = [build_dashboard_match_state(match, now=now) for match in matches]
        live_matches = [c for c in match_cards if c["is_live_now"]]
        upcoming_matches = [c for c in match_cards if c["days_to_match"] is not None and c["days_to_match"] >= 0]
        past_matches = [c for c in match_cards if c["days_to_match"] is not None and c["days_to_match"] < 0]
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

        context.update({
            "stats": stats,
            "now": now,
            "prep_window_days": PREP_WINDOW_DAYS,
            "selected_view": selected_view,
            "live_matches": live_matches[:8],
            "ready_for_ticket_sale_matches": ready_for_ticket_sale_matches[:8],
            "prep_alert_matches": prep_alert_matches[:8],
            "starting_soon_matches": starting_soon_matches[:8],
            "matches_needing_reports": matches_needing_reports[:8],
            "upcoming_matches": upcoming_matches[:12],
            "past_matches": past_matches[:12],
            "featured_matches": featured_matches[:12],
        })
        return context
