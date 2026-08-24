
from datetime import datetime, timedelta

from django.core.paginator import Paginator
from django.db.models import Case, IntegerField, Prefetch, Value, When

from checklists.models import MatchChecklistItem
from matches.utils import combine_match_datetime
from operations.models import MatchActivityLog

POST_MATCH_CATEGORY_NAME = "Post Match"
LIVE_MATCH_DURATION_HOURS = 2
PREP_WINDOW_DAYS = 20
STARTING_SOON_HOURS = 48
ACTIVITY_LOG_PAGE_SIZE = 8
ROSHAN_LEAGUE_NAME_HINT = "roshan"

MISSING_REQUIREMENTS_EXCLUDED_CATEGORY_NAMES = {POST_MATCH_CATEGORY_NAME}
MISSING_REQUIREMENTS_EXCLUDED_ITEM_TITLES = {"Result", "Report", "Final Result", "Match Report"}


def get_roshan_league_competition():
    from matches.models import Competition

    return Competition.objects.filter(is_active=True, name_en__icontains=ROSHAN_LEAGUE_NAME_HINT).first()


def get_coordinators_for_matches(matches_queryset):
    """Coordinators (home-club owners) among a set of matches - shared by
    the SPL Report and Calendar coordinator filters."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    coordinator_ids = matches_queryset.values_list("home_club__owner_id", flat=True).distinct()
    return User.objects.filter(id__in=coordinator_ids).order_by("username")


def get_missing_requirements_pending_items(match):
    """Pending checklist items for the Missing Operational Requirements report
    - shared by the report list and the match popup so both stay in sync."""
    return (
        match.checklist_items.select_related("template_item__category", "completed_by")
        .filter(is_active=True)
        .exclude(status=MatchChecklistItem.Status.DONE)
        .exclude(template_item__category__name__in=MISSING_REQUIREMENTS_EXCLUDED_CATEGORY_NAMES)
        .exclude(template_item__title__in=MISSING_REQUIREMENTS_EXCLUDED_ITEM_TITLES)
        .order_by("template_item__category__sort_order", "template_item__sort_order", "id")
    )


def get_match_detail_prefetch():
    return Prefetch(
        "checklist_items",
        queryset=MatchChecklistItem.objects.select_related(
            "template_item__category",
            "completed_by",
        ).filter(is_active=True),
    )


def get_dashboard_prefetch():
    return Prefetch(
        "checklist_items",
        queryset=MatchChecklistItem.objects.select_related(
            "template_item__category",
        ).filter(is_active=True),
    )


def _get_active_items(match):
    prefetched = getattr(match, "prefetched_active_checklist_items", None)
    if prefetched is not None:
        return list(prefetched)
    prefetched = getattr(match, "checklist_items", None)
    if prefetched is not None and hasattr(prefetched, "all"):
        return list(prefetched.all())
    return list(
        match.checklist_items.select_related("template_item__category", "completed_by").filter(is_active=True)
    )


def build_dashboard_match_state(match, now):
    match_dt = combine_match_datetime(match)
    active_items = _get_active_items(match)

    post_match_items = [
        item for item in active_items
        if item.template_item.category.name == POST_MATCH_CATEGORY_NAME
    ]
    non_post_match_items = [
        item for item in active_items
        if item.template_item.category.name != POST_MATCH_CATEGORY_NAME
    ]

    total_items = len(active_items)
    done_items = sum(1 for item in active_items if item.status == MatchChecklistItem.Status.DONE)
    delayed_items = sum(1 for item in active_items if item.status == MatchChecklistItem.Status.DELAYED)
    in_progress_items = sum(1 for item in active_items if item.status == MatchChecklistItem.Status.IN_PROGRESS)
    not_started_items = sum(1 for item in active_items if item.status == MatchChecklistItem.Status.NOT_STARTED)

    post_match_total = len(post_match_items)
    post_match_done = sum(1 for item in post_match_items if item.status == MatchChecklistItem.Status.DONE)
    post_match_pending = post_match_total - post_match_done

    non_post_match_total = len(non_post_match_items)
    non_post_match_done = sum(1 for item in non_post_match_items if item.status == MatchChecklistItem.Status.DONE)
    non_post_match_pending = non_post_match_total - non_post_match_done

    days_to_match = None
    hours_to_match = None
    prep_window_started = False
    is_today = False
    is_past = False
    starting_within_48h = False
    match_finished = False

    if match_dt:
        from django.utils import timezone
        local_match_dt = timezone.localtime(match_dt)
        diff = local_match_dt - now
        hours_to_match = diff.total_seconds() / 3600
        days_to_match = (local_match_dt.date() - now.date()).days
        prep_window_started = days_to_match <= PREP_WINDOW_DAYS
        is_today = local_match_dt.date() == now.date()
        is_past = local_match_dt < now
        starting_within_48h = 0 <= hours_to_match <= STARTING_SOON_HOURS

        # A match is only "live" up to its scheduled end - use match_end_time
        # when the coordinator set one, otherwise fall back to a standard
        # LIVE_MATCH_DURATION_HOURS window after kickoff.
        if match.match_end_time:
            end_dt = datetime.combine(match.event_date, match.match_end_time)
            if timezone.is_naive(end_dt):
                end_dt = timezone.make_aware(end_dt)
            end_dt = timezone.localtime(end_dt)
        else:
            end_dt = local_match_dt + timedelta(hours=LIVE_MATCH_DURATION_HOURS)
        match_finished = now >= end_dt

    ready_for_ticket_sale = non_post_match_total > 0 and non_post_match_pending == 0

    from matches.models import Match
    published_is_live = match.cms_status == Match.Status.PUBLISHED and not match_finished
    auto_live_by_ops = (
        not is_past
        and prep_window_started
        and non_post_match_total > 0
        and non_post_match_pending == 0
    )
    is_live_now = published_is_live or auto_live_by_ops
    needs_reports = is_past and post_match_pending > 0

    if is_live_now:
        alert_level = "success"
        alert_text = "Live on CMS" if published_is_live else "Live by Schedule"
    elif days_to_match is None:
        alert_level = "neutral"
        alert_text = "Missing match date"
    elif needs_reports:
        alert_level = "danger"
        alert_text = "Reports Pending"
    elif is_past:
        alert_level = "neutral"
        alert_text = "Match Finished"
    elif ready_for_ticket_sale:
        alert_level = "success"
        alert_text = "Ready for Ticket Sale"
    elif days_to_match <= 2 and non_post_match_pending > 0:
        alert_level = "danger"
        alert_text = "Critical Prep"
    elif days_to_match <= 5 and non_post_match_pending > 0:
        alert_level = "warning"
        alert_text = "Urgent Prep"
    elif days_to_match <= 10 and non_post_match_pending > 0:
        alert_level = "warning"
        alert_text = "Needs Attention"
    elif days_to_match <= PREP_WINDOW_DAYS and non_post_match_pending > 0:
        alert_level = "info"
        alert_text = "Prep Window Started"
    else:
        alert_level = "neutral"
        alert_text = "On Track"

    return {
        "match": match,
        "match_dt": match_dt,
        "days_to_match": days_to_match,
        "hours_to_match": hours_to_match,
        "prep_window_started": prep_window_started,
        "is_today": is_today,
        "is_past": is_past,
        "is_live_now": is_live_now,
        "match_finished": match_finished,
        "starting_within_48h": starting_within_48h,
        "ready_for_ticket_sale": ready_for_ticket_sale,
        "needs_reports": needs_reports,
        "published_is_live": published_is_live,
        "auto_live_by_ops": auto_live_by_ops,
        "alert_level": alert_level,
        "alert_text": alert_text,
        "total_items": total_items,
        "done_items": done_items,
        "delayed_items": delayed_items,
        "in_progress_items": in_progress_items,
        "not_started_items": not_started_items,
        "post_match_total": post_match_total,
        "post_match_done": post_match_done,
        "post_match_pending": post_match_pending,
        "non_post_match_total": non_post_match_total,
        "non_post_match_done": non_post_match_done,
        "non_post_match_pending": non_post_match_pending,
    }


KV_CATEGORY_NAME = "KVs"


def is_kv_ready(match):
    """True if every active "KVs" (Key Visuals) checklist item for this match
    is Done - shared by the SPL Report readiness score and the Missing
    Operational Requirements KV filter."""
    kv_items = [item for item in _get_active_items(match) if item.template_item.category.name == KV_CATEGORY_NAME]
    return bool(kv_items) and all(item.status == MatchChecklistItem.Status.DONE for item in kv_items)


def build_spl_report_row(match):
    active_items = _get_active_items(match)
    non_post_match_items = [
        item for item in active_items
        if item.template_item.category.name != POST_MATCH_CATEGORY_NAME
    ]

    kv_ready = is_kv_ready(match)
    webook_ready = bool(non_post_match_items) and all(
        item.status == MatchChecklistItem.Status.DONE for item in non_post_match_items
    )

    non_post_match_total = len(non_post_match_items)
    non_post_match_done = sum(1 for item in non_post_match_items if item.status == MatchChecklistItem.Status.DONE)
    readiness_percent = round((non_post_match_done / non_post_match_total) * 100) if non_post_match_total > 0 else 0

    return {
        "match": match,
        "kv_ready": kv_ready,
        "webook_ready": webook_ready,
        "readiness_percent": readiness_percent,
    }


def build_match_progress_context(match):
    active_items = _get_active_items(match)
    required_items = [item for item in active_items if item.template_item.is_required]

    total_items = len(active_items)
    done_items = sum(1 for item in active_items if item.status == MatchChecklistItem.Status.DONE)
    delayed_items = sum(1 for item in active_items if item.status == MatchChecklistItem.Status.DELAYED)
    not_started_items = sum(1 for item in active_items if item.status == MatchChecklistItem.Status.NOT_STARTED)
    in_progress_items = sum(1 for item in active_items if item.status == MatchChecklistItem.Status.IN_PROGRESS)

    required_total = len(required_items)
    required_done = sum(1 for item in required_items if item.status == MatchChecklistItem.Status.DONE)
    required_delayed = sum(1 for item in required_items if item.status == MatchChecklistItem.Status.DELAYED)

    progress_percent = round((done_items / total_items) * 100) if total_items > 0 else 0

    return {
        "match": match,
        "total_items": total_items,
        "done_items": done_items,
        "delayed_items": delayed_items,
        "not_started_count": not_started_items,
        "in_progress_count": in_progress_items,
        "required_total": required_total,
        "required_done": required_done,
        "required_delayed": required_delayed,
        "progress_percent": progress_percent,
    }


def get_match_activity_page_context(match, page=1, per_page=ACTIVITY_LOG_PAGE_SIZE):
    logs_qs = match.activity_logs.select_related("user").all().order_by("-created_at", "-id")
    paginator = Paginator(logs_qs, per_page)
    page_obj = paginator.get_page(page)
    return {
        "match": match,
        "page_obj": page_obj,
        "activity_logs": page_obj.object_list,
        "has_more_logs": page_obj.has_next(),
        "next_logs_page": page_obj.next_page_number() if page_obj.has_next() else None,
    }


def checklist_item_matches_filter(status, selected_filter):
    """Shared by the full checklist view and the single-item update response,
    so a card that no longer matches the active filter (e.g. marked Done
    while viewing "Open Only") disappears immediately instead of drifting
    out of sync with a full-page filter re-fetch."""
    if selected_filter == "not_started":
        return status == MatchChecklistItem.Status.NOT_STARTED
    if selected_filter == "in_progress":
        return status == MatchChecklistItem.Status.IN_PROGRESS
    if selected_filter == "delayed":
        return status == MatchChecklistItem.Status.DELAYED
    if selected_filter == "done":
        return status == MatchChecklistItem.Status.DONE
    if selected_filter == "open":
        return status != MatchChecklistItem.Status.DONE
    return True  # "all"


def build_match_detail_side_context(match, selected_filter="open"):
    base_items = _get_active_items(match)
    ordered_items = sorted(
        base_items,
        key=lambda item: (
            item.template_item.category.sort_order,
            {
                MatchChecklistItem.Status.NOT_STARTED: 0,
                MatchChecklistItem.Status.IN_PROGRESS: 1,
                MatchChecklistItem.Status.DELAYED: 2,
                MatchChecklistItem.Status.DONE: 3,
            }.get(item.status, 9),
            item.template_item.sort_order,
            item.id,
        ),
    )

    checklist_items = [
        item for item in ordered_items if checklist_item_matches_filter(item.status, selected_filter)
    ]

    grouped = {}
    for checklist_item in checklist_items:
        category = checklist_item.template_item.category
        grouped.setdefault(category, []).append(checklist_item)

    context = {
        "match": match,
        "grouped_checklist": grouped,
        "selected_filter": selected_filter,
        "not_started_items": [item for item in ordered_items if item.status == MatchChecklistItem.Status.NOT_STARTED],
        "in_progress_items": [item for item in ordered_items if item.status == MatchChecklistItem.Status.IN_PROGRESS],
        "delayed_items_list": [item for item in ordered_items if item.status == MatchChecklistItem.Status.DELAYED],
    }
    context.update(build_match_progress_context(match))
    context.update(get_match_activity_page_context(match, page=1))
    return context


def build_checklist_queryset_for_detail(match):
    return (
        match.checklist_items.select_related("template_item__category", "completed_by")
        .filter(is_active=True)
        .annotate(
            status_priority=Case(
                When(status=MatchChecklistItem.Status.NOT_STARTED, then=Value(0)),
                When(status=MatchChecklistItem.Status.IN_PROGRESS, then=Value(1)),
                When(status=MatchChecklistItem.Status.DELAYED, then=Value(2)),
                When(status=MatchChecklistItem.Status.DONE, then=Value(3)),
                default=Value(9),
                output_field=IntegerField(),
            )
        )
        .order_by(
            "template_item__category__sort_order",
            "status_priority",
            "template_item__sort_order",
            "id",
        )
    )


def log_match_activity(match, action, description, user=None):
    MatchActivityLog.objects.create(
        match=match,
        user=user if getattr(user, "is_authenticated", False) else None,
        action=action,
        description=description,
    )
