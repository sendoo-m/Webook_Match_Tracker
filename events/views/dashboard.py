from datetime import datetime, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.views.generic import TemplateView

from ..models import Event
from ..permissions import EventScopedQuerysetMixin
from ..utils import combine_event_datetime

LIVE_EVENT_DURATION_HOURS = 3


class EventsDashboardView(LoginRequiredMixin, EventScopedQuerysetMixin, TemplateView):
    template_name = "events/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.localtime()

        events = self.filter_events_queryset(
            Event.objects.select_related("category", "category__group", "venue")
            .order_by("event_date", "start_time")
        )

        cards = []
        for event in events:
            event_dt = combine_event_datetime(event)
            is_past = bool(event_dt and event_dt <= now)
            if event.end_time and event.event_date:
                end_dt = datetime.combine(event.event_date, event.end_time)
                if timezone.is_naive(end_dt):
                    end_dt = timezone.make_aware(end_dt)
            else:
                end_dt = event_dt + timedelta(hours=LIVE_EVENT_DURATION_HOURS) if event_dt else None
            is_live_now = bool(event_dt and end_dt and event_dt <= now < end_dt)
            days_to_event = (event.event_date - now.date()).days if event.event_date else None

            cards.append({
                "event": event,
                "is_past": is_past,
                "is_live_now": is_live_now,
                "days_to_event": days_to_event,
            })

        upcoming_or_live = [c for c in cards if not c["is_past"] or c["is_live_now"]]
        upcoming_or_live.sort(key=lambda c: (c["days_to_event"] if c["days_to_event"] is not None else 9999,))

        by_group = {}
        for card in upcoming_or_live:
            group = card["event"].category.group
            by_group.setdefault(group, []).append(card)

        context.update({
            "now": now,
            "cards_by_group": sorted(by_group.items(), key=lambda kv: kv[0].sort_order),
            "total_upcoming": len(upcoming_or_live),
            "live_count": sum(1 for c in upcoming_or_live if c["is_live_now"]),
        })
        return context
