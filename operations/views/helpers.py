
from datetime import datetime, timedelta

from django.core.paginator import Paginator
from django.db.models import Case, IntegerField, Prefetch, Value, When

from checklists.models import MatchChecklistItem
from matches.utils import combine_match_datetime
from operations.models import ClubPricingPlan, MatchActivityLog

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


def get_round_date_ranges(matches_queryset):
    """{round_number: (start_date, end_date)} across every dated,
    round-numbered match in the queryset - a round's own fixtures usually
    span a few days rather than a single date, so both ends matter for
    deciding whether "today" falls inside it. Shared by
    get_current_round_number and the Rounds strip's chip tooltips."""
    ranges = {}
    for round_number, event_date in matches_queryset.exclude(round_number__isnull=True).exclude(
        event_date__isnull=True
    ).values_list("round_number", "event_date"):
        start, end = ranges.get(round_number, (event_date, event_date))
        ranges[round_number] = (min(start, event_date), max(end, event_date))
    return ranges


def get_current_round_number(round_ranges, today):
    """The round whose date range actually spans today - the "current"
    matchweek to auto-select/highlight on the dashboards' Rounds strip.
    Takes the {round_number: (start, end)} dict from get_round_date_ranges
    (rather than a queryset) so a caller that also needs the ranges for
    chip tooltips only has to compute them once.

    If more than one round's range contains today (a postponed match can
    stretch an earlier round's range past a later round that's already
    under way), the higher round number wins - round numbers progress
    chronologically, so an earlier round reaching this far is the outlier,
    not the later round's absence. Between rounds (today falls in the gap
    after one round ends and before the next starts), the next upcoming
    round counts as current; once the last round has finished, that last
    round stays current. Returns None if round_ranges is empty.
    """
    if not round_ranges:
        return None

    containing = [r for r, (start, end) in round_ranges.items() if start <= today <= end]
    if containing:
        return max(containing)

    upcoming = [r for r, (start, _end) in round_ranges.items() if start > today]
    if upcoming:
        return min(upcoming, key=lambda r: round_ranges[r][0])
    return max(round_ranges, key=lambda r: round_ranges[r][1])


def get_selectable_clubs(matches_queryset):
    """Single source of truth for every "Club"/"Home Team"/"Away Team"
    filter dropdown in the app, so every page's option list is identical.
    A club qualifies if it appears on EITHER side of a match in this
    queryset. Always excludes is_test_club records (dummy fixtures with no
    real matches - see Club.is_test_club) so they never leak into a live
    filter, report, or stat.
    """
    from django.db.models import Q

    from matches.models import Club

    return (
        Club.objects.filter(Q(home_matches__in=matches_queryset) | Q(away_matches__in=matches_queryset))
        .filter(is_active=True, is_test_club=False)
        .distinct()
        .order_by("name_ar")
    )


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


def get_missing_requirements_eligible_items_count(match):
    """Total active, non-excluded checklist items for a match (same scope
    as get_missing_requirements_pending_items, minus the DONE exclusion) -
    the denominator for a "done/total" progress indicator on the Missing
    Operational Requirements report. Filters in Python over
    match.checklist_items.all() rather than a fresh queryset, so it reuses
    get_match_detail_prefetch()'s prefetched items instead of issuing one
    extra query per match in what's already a per-match loop.
    """
    return sum(
        1
        for item in match.checklist_items.all()
        if item.is_active
        and item.template_item.category.name not in MISSING_REQUIREMENTS_EXCLUDED_CATEGORY_NAMES
        and item.template_item.title not in MISSING_REQUIREMENTS_EXCLUDED_ITEM_TITLES
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


def auto_complete_non_post_match_items(match, user):
    """Once a match is Published with its Webook ticket link set, every
    pre-match checklist item is effectively confirmed done by that action
    itself - marking each one by hand afterward is pure busywork. Post
    Match items are the one exception, left untouched, since those
    genuinely can't be done until the match has actually been played.

    Only touches items not already Done (so it never clobbers an existing
    completed_by/completed_at), and only ever runs from the two call sites
    that already confirmed both conditions (Published status + a Webook
    link) are true. Returns the list of items that were actually changed,
    so the caller can decide whether anything needs logging/refreshing.
    """
    from django.utils import timezone

    items = list(
        match.checklist_items.select_related("template_item__category")
        .filter(is_active=True)
        .exclude(template_item__category__name=POST_MATCH_CATEGORY_NAME)
        .exclude(status=MatchChecklistItem.Status.DONE)
    )
    if not items:
        return items

    now = timezone.now()
    for item in items:
        item.status = MatchChecklistItem.Status.DONE
        item.completed_by = user if getattr(user, "is_authenticated", False) else None
        item.completed_at = now
    MatchChecklistItem.objects.bulk_update(items, ["status", "completed_by", "completed_at"])
    return items


def _split_by_post_match(active_items):
    """Every "is this match ready" computation in the app needs to treat
    Post Match items separately - they can't legitimately be Done until
    the match has actually been played, so they're excluded from anything
    framed as pre-match readiness. Centralized here so the three call
    sites (dashboard state, SPL report row, match-detail progress) can't
    drift on the definition of "post match" vs. everything else."""
    post_match_items = [
        item for item in active_items
        if item.template_item.category.name == POST_MATCH_CATEGORY_NAME
    ]
    non_post_match_items = [
        item for item in active_items
        if item.template_item.category.name != POST_MATCH_CATEGORY_NAME
    ]
    return non_post_match_items, post_match_items


def build_dashboard_match_state(match, now):
    match_dt = combine_match_datetime(match)
    active_items = _get_active_items(match)

    non_post_match_items, post_match_items = _split_by_post_match(active_items)

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


PLANNED_RELEASE_LEAD_DAYS = 20


def compute_release_status(match, today):
    """Where a match's ticket sale release stands relative to the "must go
    on sale 20 days before kickoff" rule - shared by the Match Release
    Schedule page and anywhere else that needs to know if a release is late.

    Returns a dict:
        planned_release_date: date, or None if the match has no event_date
                               at all (nothing to compute against yet).
        status: "live_missing_release_date" | "released_on_time" |
                "released_late" | "delayed" | "due_today" | "upcoming" |
                None (no event_date).
        delay_days: how many days late - 0 unless status is "released_late"
                    or "delayed".

    "released_*" covers matches whose tickets are already live
    (actual_release_at is set); "delayed"/"due_today"/"upcoming" describe an
    as-yet-unreleased match relative to today.

    "live_missing_release_date" is its own case, checked before the
    delayed/upcoming math: a match already Published on the CMS with no
    actual_release_at recorded is a data gap, not a "still waiting" delay -
    the normal auto-stamp on publish (see MatchCMSStatusUpdateView) missed
    it, likely because it went live through an older import/bulk path
    instead. Surfacing this separately is what let a real backlog of ~7
    such matches actually get found and fixed, instead of being silently
    miscounted as "delayed" or even "upcoming".
    """
    if not match.event_date:
        return {"planned_release_date": None, "status": None, "delay_days": 0}

    planned_release_date = match.event_date - timedelta(days=PLANNED_RELEASE_LEAD_DAYS)

    if match.actual_release_at:
        from django.utils import timezone

        actual_date = timezone.localtime(match.actual_release_at).date()
        delay_days = (actual_date - planned_release_date).days
        if delay_days > 0:
            return {"planned_release_date": planned_release_date, "status": "released_late", "delay_days": delay_days}
        return {"planned_release_date": planned_release_date, "status": "released_on_time", "delay_days": 0}

    from matches.models import Match

    if match.cms_status == Match.Status.PUBLISHED:
        return {"planned_release_date": planned_release_date, "status": "live_missing_release_date", "delay_days": 0}

    if today > planned_release_date:
        return {
            "planned_release_date": planned_release_date,
            "status": "delayed",
            "delay_days": (today - planned_release_date).days,
        }
    if today == planned_release_date:
        return {"planned_release_date": planned_release_date, "status": "due_today", "delay_days": 0}
    return {"planned_release_date": planned_release_date, "status": "upcoming", "delay_days": 0}


KV_CATEGORY_NAME = "KVs"


def is_kv_ready(match):
    """True if every active "KVs" (Key Visuals) checklist item for this match
    is Done - shared by the SPL Report readiness score and the Missing
    Operational Requirements KV filter."""
    kv_items = [item for item in _get_active_items(match) if item.template_item.category.name == KV_CATEGORY_NAME]
    return bool(kv_items) and all(item.status == MatchChecklistItem.Status.DONE for item in kv_items)


def build_spl_report_row(match, now):
    active_items = _get_active_items(match)
    non_post_match_items, post_match_items = _split_by_post_match(active_items)

    kv_ready = is_kv_ready(match)
    webook_ready = bool(non_post_match_items) and all(
        item.status == MatchChecklistItem.Status.DONE for item in non_post_match_items
    )

    non_post_match_total = len(non_post_match_items)
    non_post_match_done = sum(1 for item in non_post_match_items if item.status == MatchChecklistItem.Status.DONE)
    readiness_percent = round((non_post_match_done / non_post_match_total) * 100) if non_post_match_total > 0 else 0

    post_match_total = len(post_match_items)
    post_match_done = sum(1 for item in post_match_items if item.status == MatchChecklistItem.Status.DONE)

    # Reuses the same live/finished computation as every other match view
    # (dashboard, calendar) so the report's "Match Status" column always
    # agrees with what's shown everywhere else.
    match_state = build_dashboard_match_state(match, now)

    # Surfaces the club's own pricing-plan submission (version, category
    # prices/file, SPL decision) everywhere this row shape is already used
    # - SPL Report, SPL Approvals, Finished Matches, and match_spl_info_box
    # via MatchDetailView/cms.py/spl/views/info.py - without wiring it into
    # each of those call sites separately. See ClubPricingPlan's own
    # docstring for why it's kept a fully separate model from Match's
    # ticketing_plan_approved boolean.
    current_pricing_plan = (
        ClubPricingPlan.objects.filter(match=match).select_related("club").order_by("-version").first()
    )

    return {
        "match": match,
        "kv_ready": kv_ready,
        "webook_ready": webook_ready,
        "readiness_percent": readiness_percent,
        "post_match_total": post_match_total,
        "post_match_done": post_match_done,
        "needs_reports": match_state["needs_reports"],
        "is_live_now": match_state["is_live_now"],
        "match_finished": match_state["match_finished"],
        "is_today": match_state["is_today"],
        "days_to_match": match_state["days_to_match"],
        "current_pricing_plan": current_pricing_plan,
    }


def get_match_lifecycle_status(card):
    """Single, mutually-exclusive classification of where a match stands
    right now - "tbc" (no date yet), "past" (finished), "live", "happening"
    (kickoff has passed but it isn't flagged live), or "upcoming".

    This is the one place that decides which of those five buckets a match
    falls into - compute_round_stats' counts and every individual match
    status badge (round preview cards) both call this, so a match is never
    labeled one thing in the stats card and something else on its own card.
    Replaces the old per-card badge, which fell back to showing the raw CMS
    status (e.g. "Draft") when a match wasn't live/finished/today - a second,
    inconsistent vocabulary layered on top of this one that people found
    confusing.
    """
    match = card["match"]
    if match.event_date is None:
        return "tbc"
    if card["match_finished"]:
        return "past"
    if card["is_live_now"]:
        return "live"
    if card["is_past"]:
        return "happening"
    return "upcoming"


def compute_round_stats(round_cards, today):
    """Per-round summary for the Rounds section's stats card, scoped to the
    round the visitor is looking at (not the whole league).

    Every match falls into exactly one of live/happening/upcoming/past/tbc
    (checked in that priority order) so the five counts always add up to
    match_count - deliberately mutually exclusive, unlike the page-wide
    League Stats buckets, since an early "Ready" bucket here proved
    confusing (unclear what it counted) and got replaced by this clearer,
    non-overlapping breakdown:
        live: is_live_now (published or auto-live by schedule).
        happening: kickoff time has strictly passed and the match hasn't
            finished yet, but it isn't flagged is_live_now - i.e. it's
            actually being played right now by the clock, whatever the
            CMS/checklist state says. Kept separate from "live" (which
            reflects ops' own live flag, not just the clock) so this bucket
            answers "how many matches are literally on the pitch right now"
            without double-counting ones already shown as Live.
        upcoming: has a match date, kickoff hasn't happened yet.
        past: match already finished.
        tbc: no match date set yet at all.
    Plus two release-tracking counts (reusing compute_release_status, the
    same "20 days before kickoff" rule as the Match Release Schedule page)
    and one ticketing-plan count:
        released_on_time: actual_release_at recorded, on/before the
            20-days-before-kickoff deadline.
        delayed_release: either already released past that deadline, or
            still unreleased with the deadline already passed.
        plan_approvals: SPL has approved the ticketing plan.

    round_cards is the list of build_dashboard_match_state dicts already
    filtered down to one round (same list used to render its match cards),
    so this never re-queries.
    """
    live_count = 0
    happening_count = 0
    upcoming_count = 0
    past_count = 0
    tbc_count = 0
    released_on_time_count = 0
    delayed_release_count = 0
    plan_approvals_count = 0

    for card in round_cards:
        match = card["match"]

        status = get_match_lifecycle_status(card)
        if status == "tbc":
            tbc_count += 1
        elif status == "past":
            past_count += 1
        elif status == "live":
            live_count += 1
        elif status == "happening":
            happening_count += 1
        else:
            upcoming_count += 1

        release_status = compute_release_status(match, today)["status"]
        if release_status == "released_on_time":
            released_on_time_count += 1
        elif release_status in ("delayed", "released_late"):
            delayed_release_count += 1

        if match.ticketing_plan_approved:
            plan_approvals_count += 1

    return {
        "match_count": len(round_cards),
        "live_count": live_count,
        "happening_count": happening_count,
        "upcoming_count": upcoming_count,
        "past_count": past_count,
        "tbc_count": tbc_count,
        "released_on_time_count": released_on_time_count,
        "delayed_release_count": delayed_release_count,
        "plan_approvals_count": plan_approvals_count,
    }


def compute_spl_home_stats(match_cards):
    """Live/In Progress/Upcoming/Finished counts for the page-wide League
    Stats cards at the top of the SPL dashboard. "In Progress" reuses the
    existing Match.Status.IN_PROGRESS CMS prep state; Live/Upcoming/Finished
    reuse the is_live_now/match_finished flags already computed per match by
    build_dashboard_match_state.

    in_progress_count excludes match_finished matches, matching exactly
    what the "Upcoming & Live Matches" table's own status=in_progress
    filter shows (see build_viewer_context) - without this, a match whose
    CMS prep was simply never updated after it was actually played would
    inflate this count while never appearing in the table the card links
    to, since that table excludes finished matches by default.
    """
    from matches.models import Match

    return {
        "live_count": sum(1 for c in match_cards if c["is_live_now"]),
        "in_progress_count": sum(
            1 for c in match_cards
            if c["match"].cms_status == Match.Status.IN_PROGRESS and not c["match_finished"]
        ),
        "upcoming_count": sum(1 for c in match_cards if not c["is_live_now"] and not c["match_finished"]),
        "finished_count": sum(1 for c in match_cards if c["match_finished"]),
    }


def build_match_progress_context(match):
    active_items = _get_active_items(match)
    required_items = [item for item in active_items if item.template_item.is_required]
    non_post_match_items, post_match_items = _split_by_post_match(active_items)

    total_items = len(active_items)
    done_items = sum(1 for item in active_items if item.status == MatchChecklistItem.Status.DONE)
    delayed_items = sum(1 for item in active_items if item.status == MatchChecklistItem.Status.DELAYED)
    not_started_items = sum(1 for item in active_items if item.status == MatchChecklistItem.Status.NOT_STARTED)
    in_progress_items = sum(1 for item in active_items if item.status == MatchChecklistItem.Status.IN_PROGRESS)

    required_total = len(required_items)
    required_done = sum(1 for item in required_items if item.status == MatchChecklistItem.Status.DONE)
    required_delayed = sum(1 for item in required_items if item.status == MatchChecklistItem.Status.DELAYED)

    progress_percent = round((done_items / total_items) * 100) if total_items > 0 else 0

    # Split out from progress_percent (which blends Post Match in with
    # everything else) so the UI can show "Admin Setup" completion - the
    # part that's actually done before kickoff - separately from the
    # post-match result/report, which can't be filed until after the
    # match is played. See auto_complete_non_post_match_items.
    non_post_match_total = len(non_post_match_items)
    non_post_match_done = sum(1 for item in non_post_match_items if item.status == MatchChecklistItem.Status.DONE)
    non_post_match_percent = round((non_post_match_done / non_post_match_total) * 100) if non_post_match_total > 0 else 0

    post_match_total = len(post_match_items)
    post_match_done = sum(1 for item in post_match_items if item.status == MatchChecklistItem.Status.DONE)
    post_match_percent = round((post_match_done / post_match_total) * 100) if post_match_total > 0 else 0

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
        "non_post_match_total": non_post_match_total,
        "non_post_match_done": non_post_match_done,
        "non_post_match_percent": non_post_match_percent,
        "post_match_total": post_match_total,
        "post_match_done": post_match_done,
        "post_match_percent": post_match_percent,
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
