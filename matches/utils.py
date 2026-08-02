# matches/utils.py

from datetime import datetime

from django.utils import timezone


def combine_match_datetime(match):
    """
    يدمج event_date و match_start_time في datetime واحد timezone-aware.
    لو مفيش وقت محدد، يفترض بداية اليوم بدل ما يرجع None.
    يرجع None فقط لو مفيش تاريخ للمباراة أصلاً.
    """
    if not match.event_date:
        return None

    start_time = getattr(match, "match_start_time", None)
    if start_time:
        dt = datetime.combine(match.event_date, start_time)
    else:
        dt = datetime.combine(match.event_date, datetime.min.time())

    if timezone.is_naive(dt):
        return timezone.make_aware(dt)
    return dt