from datetime import datetime

from django.utils import timezone


def combine_event_datetime(event):
    """Combines event_date and start_time into one timezone-aware datetime -
    events-app equivalent of matches/utils.py:combine_match_datetime.
    Returns None only if the event has no date at all."""
    if not event.event_date:
        return None

    if event.start_time:
        dt = datetime.combine(event.event_date, event.start_time)
    else:
        dt = datetime.combine(event.event_date, datetime.min.time())

    if timezone.is_naive(dt):
        return timezone.make_aware(dt)
    return dt
