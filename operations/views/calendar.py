# operations/views/calendar.py

import calendar as calendar_module
from datetime import date

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpResponseBadRequest
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import TemplateView

from matches.models import Match
from operations.permissions import MatchScopedQuerysetMixin

from .helpers import build_dashboard_match_state, get_coordinators_for_matches, get_dashboard_prefetch, get_selectable_clubs

DAY_MATCH_LIMIT = 3


class MatchCalendarView(LoginRequiredMixin, MatchScopedQuerysetMixin, TemplateView):
    template_name = "operations/calendar.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = date.today()
        now = timezone.localtime()

        try:
            year = int(self.request.GET.get("year", today.year))
            month = int(self.request.GET.get("month", today.month))
        except ValueError:
            year, month = today.year, today.month

        if month < 1:
            month, year = 12, year - 1
        elif month > 12:
            month, year = 1, year + 1

        selected_club = self.request.GET.get("club", "")
        selected_coordinator = self.request.GET.get("coordinator", "")

        # Sunday-first week, matching the region this app is built for.
        cal = calendar_module.Calendar(firstweekday=6)
        month_dates = cal.monthdatescalendar(year, month)
        first_date = month_dates[0][0]
        last_date = month_dates[-1][-1]

        matches = self.filter_matches_queryset(
            Match.objects.select_related("home_club", "away_club", "venue", "competition")
            .filter(event_date__gte=first_date, event_date__lte=last_date)
            .prefetch_related(get_dashboard_prefetch())
            .order_by("event_date", "match_start_time")
        )
        if selected_club:
            matches = matches.filter(home_club_id=selected_club)
        if selected_coordinator:
            matches = matches.filter(home_club__owner_id=selected_coordinator)
        matches_by_day = {}
        for match in matches:
            matches_by_day.setdefault(match.event_date, []).append(match)

        weeks = []
        for week in month_dates:
            week_days = []
            for day in week:
                day_matches = matches_by_day.get(day, [])
                visible_cards = []
                for m in day_matches[:DAY_MATCH_LIMIT]:
                    state = build_dashboard_match_state(m, now=now)
                    visible_cards.append({
                        "match": m,
                        "is_live_now": state["is_live_now"],
                        "is_finished": state["match_finished"],
                        "is_today": state["is_today"],
                    })
                week_days.append({
                    "date": day,
                    "in_month": day.month == month,
                    "is_today": day == today,
                    "matches": visible_cards,
                    "extra_count": max(0, len(day_matches) - DAY_MATCH_LIMIT),
                })
            weeks.append(week_days)

        prev_month, prev_year = (12, year - 1) if month == 1 else (month - 1, year)
        next_month, next_year = (1, year + 1) if month == 12 else (month + 1, year)

        # Club/Coordinator options reflect everything this user can ever
        # see, not just this month, so the dropdowns stay stable while
        # navigating.
        scoped_matches = self.filter_matches_queryset(Match.objects.all())

        context.update({
            "year": year,
            "month": month,
            "month_label": date(year, month, 1).strftime("%B %Y"),
            "weeks": weeks,
            "today": today,
            "prev_year": prev_year,
            "prev_month": prev_month,
            "next_year": next_year,
            "next_month": next_month,
            "clubs": get_selectable_clubs(scoped_matches),
            "coordinators": get_coordinators_for_matches(scoped_matches),
            "selected_club": selected_club,
            "selected_coordinator": selected_coordinator,
        })
        return context


class CalendarDayMatchesView(LoginRequiredMixin, MatchScopedQuerysetMixin, View):
    """Renders every match on one calendar day, for the "+N more" popup -
    the day cell itself only ever shows up to DAY_MATCH_LIMIT chips."""

    def get(self, request, year, month, day, *args, **kwargs):
        try:
            target_date = date(year, month, day)
        except ValueError:
            return HttpResponseBadRequest(_("Invalid date."))

        now = timezone.localtime()
        matches = self.filter_matches_queryset(
            Match.objects.select_related("home_club", "away_club", "venue", "competition")
            .filter(event_date=target_date)
            .prefetch_related(get_dashboard_prefetch())
            .order_by("match_start_time", "id")
        )
        cards = [build_dashboard_match_state(m, now=now) for m in matches]
        html = render_to_string(
            "operations/partials/calendar_day_matches_popup.html",
            {"target_date": target_date, "cards": cards},
            request=request,
        )
        return HttpResponse(html)
