# operations/views/calendar.py

import calendar as calendar_module
from datetime import date

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from matches.models import Match
from operations.permissions import MatchScopedQuerysetMixin

DAY_MATCH_LIMIT = 3


class MatchCalendarView(LoginRequiredMixin, MatchScopedQuerysetMixin, TemplateView):
    template_name = "operations/calendar.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = date.today()

        try:
            year = int(self.request.GET.get("year", today.year))
            month = int(self.request.GET.get("month", today.month))
        except ValueError:
            year, month = today.year, today.month

        if month < 1:
            month, year = 12, year - 1
        elif month > 12:
            month, year = 1, year + 1

        # Sunday-first week, matching the region this app is built for.
        cal = calendar_module.Calendar(firstweekday=6)
        month_dates = cal.monthdatescalendar(year, month)
        first_date = month_dates[0][0]
        last_date = month_dates[-1][-1]

        matches = self.filter_matches_queryset(
            Match.objects.select_related("home_club", "away_club", "venue", "competition")
            .filter(event_date__gte=first_date, event_date__lte=last_date)
            .order_by("event_date", "match_start_time")
        )
        matches_by_day = {}
        for match in matches:
            matches_by_day.setdefault(match.event_date, []).append(match)

        weeks = []
        for week in month_dates:
            week_days = []
            for day in week:
                day_matches = matches_by_day.get(day, [])
                week_days.append({
                    "date": day,
                    "in_month": day.month == month,
                    "is_today": day == today,
                    "matches": day_matches[:DAY_MATCH_LIMIT],
                    "extra_count": max(0, len(day_matches) - DAY_MATCH_LIMIT),
                })
            weeks.append(week_days)

        prev_month, prev_year = (12, year - 1) if month == 1 else (month - 1, year)
        next_month, next_year = (1, year + 1) if month == 12 else (month + 1, year)

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
        })
        return context
