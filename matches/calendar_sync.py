# matches/calendar_sync.py
#
# Pulls Roshan League fixtures from SPL's Google Calendar iCal feed ("Saudi
# Pro League" ECAL calendar) and creates/updates the matching Match rows.
# Syncs EVERY round by default (no Matchweek range restriction) so it can be
# run continuously/on a schedule - see the management command
# matches/management/commands/sync_roshan_calendar.py for the "keep this
# always up to date" entrypoint (wire it to Windows Task Scheduler / cron to
# run every N minutes). min_round/max_round parameters still exist for the
# case where someone wants to scope a one-off run, but default to None
# (no restriction).
#
# Why this file exists: the calendar is SPL's own fan-facing marketing feed,
# not a clean data export - inspecting the real feed while building this
# showed:
#   - each fixture appears as up to three separate VEVENTs ("Ticket Alert!"
#     reminder, "Watch live" reminder, and the actual match event) - only
#     the "match" (soccer-ball emoji) VEVENT is trusted here;
#   - and, per fixture, the "match" VEVENT itself is sometimes DUPLICATED
#     two or three times (identical UID-less repeats with the same date/time)
#     - harmless here since matches are looked up/deduped by (round, the two
#       clubs) before writing, so repeats just update the same row again;
#   - many match events still carry a placeholder kickoff time until SPL
#     confirms one (summary ends in "(Time TBC)", but DTSTART still holds
#     some arbitrary time) - these are SKIPPED rather than importing a
#     guessed time into a ticketing system, since gates_open_time,
#     match_end_time, and the ticket sale date are all derived from it.
#
# Matching key: (competition, round_number) + the two clubs (in either
# order) - NOT event_date. If SPL reschedules a fixture to a different day
# or kicks the time around, this still finds and updates the SAME match
# instead of leaving a stale row behind and creating a duplicate for the new
# date. A fixture's identity is "this round, these two teams", not "this
# specific calendar date".
#
# Called from:
#   - matches/admin.py's MatchAdmin.sync_calendar_view (Django Admin's
#     "Update Roshan League Schedule" button, POST-only after a confirm
#     page) and export_calendar_view (single-click dry-run Excel download).
#   - control_panel/views/matches.py's MatchSyncCalendarView (the same
#     button surfaced on the Control Panel's Matches page).
#   - matches/management/commands/sync_roshan_calendar.py (`python manage.py
#     sync_roshan_calendar`, for scheduled/continuous runs).
# All four call sync_roshan_league_from_calendar() below; dry_run=True (used
# by both Excel-export buttons) builds the same rows without touching the
# database.

import os
import random
import re
from datetime import timedelta
from zoneinfo import ZoneInfo

import requests
from django.db.models import Q
from django.utils.text import slugify
from icalendar import Calendar

from checklists.services import attach_default_checklist_items

from .models import Club, Competition, Match, Venue

RIYADH_TZ = ZoneInfo("Asia/Riyadh")
UTC_TZ = ZoneInfo("UTC")

# The calendar is SPL's public fan-facing feed, not owned by this project -
# its "secret address" embeds a private access token, so it's read from an
# environment variable (see .env / .env.example) instead of being hardcoded
# here or in settings.py, to avoid leaking that token into git history.
# The PUBLIC address below is used only as a fallback default: as observed
# while building this importer, SPL's public "basic.ics" address currently
# returns a calendar with ZERO events (sharing is set to free/busy only) -
# only the secret address actually returns fixture data, so
# MATCH_CALENDAR_ICAL_URL must be set to that secret URL for this to work.
DEFAULT_PUBLIC_ICAL_URL = (
    "https://calendar.google.com/calendar/ical/"
    "c_0fc50b34ad1686793e755f0353f12b7146e39337bc5b4dcbcb199e822197eba9"
    "%40group.calendar.google.com/public/basic.ics"
)

# Real SPL calendar SUMMARY values start with one of a few emoji depending
# on event type - only the "match" emoji is an authoritative fixture record
# ("Ticket Alert!" 🎫 and "Watch live" ▶️ are just marketing reminders for
# the same fixture, with their own unrelated placeholder times).
MATCH_EMOJI_PREFIX = "⚽️"  # "⚽️"

# SPL's own calendar labels rounds "Matchweek N" in the DESCRIPTION; "Round
# N" / "الجولة N" are kept as fallback patterns in case the wording changes
# or a different calendar is configured later.
ROUND_PATTERN = re.compile(
    r"(?:matchweek|round|الجولة)\s*#?\s*(\d+)",
    re.IGNORECASE,
)
TBC_PATTERN = re.compile(r"time\s*tbc", re.IGNORECASE)

# Matches the "RSL 26/27" / "دوري روشن 26/27" naming already used for every
# other Roshan League 26/27 match in this database (seeded by the earlier
# CSV import) - update these two constants when the season rolls over.
LEAGUE_LABEL_EN = "RSL 26/27"
LEAGUE_LABEL_AR = "دوري روشن 26/27"

TERMS_AR_DEFAULT = "لا يوجد استرجاع للمبالغ."
TERMS_EN_DEFAULT = "Refund is not allowed."

# Maps a team name as it appears on the SPL calendar to the Club.name_en it
# actually corresponds to, for known naming mismatches - mirrors the same
# alias already needed by matches/management/commands/import_rsl_club_matches.py
# for the same club, so it's a known, recurring discrepancy rather than a
# one-off typo.
CLUB_NAME_ALIASES = {
    "al diriyah club": "al diriyah",
}

# Maps a LOCATION string exactly as SPL's calendar spells it to the
# canonical "Stadium, City" Venue.name_en already used for that same real
# stadium in this database. Without this, every sync would keep recreating
# a near-duplicate Venue for these two stadiums forever, since the
# calendar's own spelling never matches the already-established name:
#   - the calendar says "Al Ettifaq Club Stadium", the existing venue is
#     named just "Ettifaq Stadium";
#   - the calendar spells Al Hazm's city "Ar Rass", the existing venue uses
#     "Al Rass".
LOCATION_ALIASES = {
    "al ettifaq club stadium, dammam": "Ettifaq Stadium, Dammam",
    "al hazm club stadium, ar rass": "Al Hazm Club Stadium, Al Rass",
}


class CalendarSyncError(Exception):
    """Raised for anything that stops the sync before any events can be
    processed (feed unreachable, feed didn't parse as iCal, no Roshan League
    Competition configured) - as opposed to one bad event, which is recorded
    in CalendarSyncResult.skipped and doesn't stop the rest of the run."""


class CalendarSyncResult:
    def __init__(self):
        self.created = 0
        self.updated = 0
        # One dict per match actually imported (or that would have been, in
        # a dry run) - shaped for both Match(**row) / setattr(...) and
        # matches.import_export.export_calendar_import_xlsx.
        self.rows = []
        # (event summary, reason) for events in the Matchweek 6-12 range
        # that couldn't be turned into a match.
        self.skipped = []
        # Match events outside Matchweek 6-12, or whose round couldn't be
        # parsed at all - not an error, just not in scope.
        self.ignored_out_of_range = 0


def _get_ical_url():
    return os.environ.get("MATCH_CALENDAR_ICAL_URL", DEFAULT_PUBLIC_ICAL_URL)


def fetch_calendar_events(ical_url=None):
    """Downloads and parses the iCal feed into a list of VEVENT components.
    Raises CalendarSyncError with a human-readable message on any network or
    parse failure, so the admin view can show it instead of a 500 page."""
    url = ical_url or _get_ical_url()
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise CalendarSyncError(f"Could not reach the Google Calendar feed: {exc}") from exc

    try:
        calendar = Calendar.from_ical(response.content)
    except (ValueError, IndexError) as exc:
        raise CalendarSyncError(f"The calendar feed did not parse as valid iCal data: {exc}") from exc

    return list(calendar.walk("VEVENT"))


def _parse_round_number(text):
    match = ROUND_PATTERN.search(text or "")
    return int(match.group(1)) if match else None


def _strip_match_summary(summary):
    """"⚽️ Al Shabab vs Al Ahli" -> ("Al Shabab", "Al Ahli", False)
    "⚽️ Al Riyadh vs Al Ittihad (Time TBC)" -> ("Al Riyadh", "Al Ittihad", True)
    Returns (None, None, False) if the text doesn't split into two teams."""
    text = summary[len(MATCH_EMOJI_PREFIX):].strip()
    time_tbc = bool(TBC_PATTERN.search(text))
    text = TBC_PATTERN.sub("", text).replace("(", "").replace(")", "").strip()
    parts = re.split(r"\s+vs\s+", text, flags=re.IGNORECASE)
    if len(parts) != 2:
        return None, None, time_tbc
    return parts[0].strip(), parts[1].strip(), time_tbc


def _find_club(name, clubs_by_name):
    if not name:
        return None
    lowered = name.strip().lower()
    lowered = CLUB_NAME_ALIASES.get(lowered, lowered)
    club = clubs_by_name.get(lowered)
    if club:
        return club
    # Fall back to a substring match in case of minor formatting drift
    # between the calendar's team names and this database's Club.name_en.
    for club_name, club in clubs_by_name.items():
        if club_name in lowered or lowered in club_name:
            return club
    return None


def _resolve_venue(location):
    """"Prince Mohammed Bin Fahd Stadium, Dammam" -> Venue(name_en="Prince
    Mohammed Bin Fahd Stadium, Dammam", city="Dammam"), get_or_create'd.
    Returns None (leave the match's venue for manual entry) for "TBC",
    blank, or a bare maps-link LOCATION with no stadium name in it.

    IMPORTANT: name_en keeps the full "Stadium, City" text as one string -
    it is NOT split down to just the stadium name. Every venue already in
    this database (both hand-entered and bulk-imported) uses that same
    "Name, City" convention for name_en; an earlier version of this function
    stored just the stadium name with city in a separate field, which never
    matched any of those existing rows and created a same-stadium duplicate
    Venue for every fixture synced from the calendar. Matching on the exact
    same full-string convention is what keeps get_or_create() finding the
    existing row instead of creating a new one.
    """
    location = (location or "").strip()
    if not location or location.upper() == "TBC" or location.lower().startswith("http"):
        return None

    location = LOCATION_ALIASES.get(location.lower(), location)

    if "," in location:
        city = location.rsplit(",", 1)[1].strip()
    else:
        city = ""

    venue, _created = Venue.objects.get_or_create(
        name_en=location,
        defaults={"name_ar": location, "city": city},
    )
    return venue


def _generate_slug(round_number, home_club, away_club, used_slugs):
    """rsl-r{round}-{home}-vs-{away}-{5 random digits}, matching the naming
    convention already used by the existing Roshan League 26/27 matches in
    this database. used_slugs tracks candidates already handed out earlier
    in this same sync run, since none of them are saved to the database yet
    at the time a dry run (Excel export) generates them."""
    base = f"rsl-r{round_number}-{slugify(home_club.name_en)}-vs-{slugify(away_club.name_en)}"
    for _ in range(20):
        candidate = f"{base}-{random.randint(10000, 99999)}"
        if candidate in used_slugs or Match.objects.filter(slug=candidate).exists():
            continue
        return candidate
    raise CalendarSyncError(f"Could not generate a unique slug for {base}")


def _get_roshan_league_competition():
    # Deliberately duplicated (not imported) from
    # operations/views/helpers.py's identical helper, to keep the matches
    # app independent of the operations app built on top of it.
    return Competition.objects.filter(is_active=True, name_en__icontains="roshan").first()


def _build_row(dt_start, location, round_number, home_club, away_club, competition, used_slugs):
    if dt_start.tzinfo is None:
        dt_start = dt_start.replace(tzinfo=UTC_TZ)
    start_local = dt_start.astimezone(RIYADH_TZ)

    match_end_local = start_local + timedelta(hours=2)  # "2 hours after kickoff", per spec
    gates_open_local = start_local - timedelta(hours=3)  # "3 hours before kickoff", per spec
    sale_starts_local = (
        start_local.replace(hour=10, minute=0, second=0, microsecond=0) - timedelta(days=20)
    )  # "10:00, 20 days before the match", per spec

    return {
        "slug": _generate_slug(round_number, home_club, away_club, used_slugs),
        "round_number": round_number,
        "home_club": home_club,
        "away_club": away_club,
        "competition": competition,
        "venue": _resolve_venue(location),
        "title_en": f"{LEAGUE_LABEL_EN} - {home_club.name_en} vs {away_club.name_en}",
        "title_ar": f"{LEAGUE_LABEL_AR} – {home_club.name_ar} ضد {away_club.name_ar}",
        "description_en": (
            f"Saudi Pro League 2026/27 season match featuring {home_club.name_en} vs {away_club.name_en}"
        ),
        "description_ar": (
            f"مباراة من الدوري السعودي للمحترفين موسم 26/27 - تجمع {home_club.name_ar} ضد {away_club.name_ar}"
        ),
        "event_date": start_local.date(),
        "match_start_time": start_local.time(),
        "match_end_time": match_end_local.time(),
        "gates_open_time": gates_open_local.time(),
        "sale_starts_at": sale_starts_local,
        "terms_ar": TERMS_AR_DEFAULT,
        "terms_en": TERMS_EN_DEFAULT,
        "has_images": False,
    }


def sync_roshan_league_from_calendar(ical_url=None, dry_run=False, min_round=None, max_round=None):
    """Fetches the calendar and creates/updates the matching Match rows for
    every round found (unless min_round/max_round are given, scoping this
    one run to a range) with a confirmed kickoff time - unless dry_run=True
    (used by the Excel export button), which builds the same rows without
    touching the database.

    Matching key for "does this match already exist": (competition,
    round_number) + the pair of clubs (checked in either home/away order, in
    case the calendar's order ever disagrees with what's already stored) -
    NOT event_date and NOT slug. Using the round + clubs as the identity
    (instead of the date) means that if SPL later reschedules a fixture to a
    different day/time, this still finds and UPDATES that same match instead
    of leaving the stale row behind and creating a duplicate for the new
    date. An existing match's slug is left untouched on update; a new one is
    only generated for brand-new matches.
    """
    events = fetch_calendar_events(ical_url)

    competition = _get_roshan_league_competition()
    if competition is None:
        raise CalendarSyncError(
            "No active Competition with 'Roshan' in its English name was found - "
            "create/activate the Roshan League Competition record first."
        )

    clubs_by_name = {club.name_en.strip().lower(): club for club in Club.objects.filter(is_active=True)}

    result = CalendarSyncResult()
    used_slugs = set()

    for event in events:
        summary = str(event.get("SUMMARY", ""))
        if not summary.startswith(MATCH_EMOJI_PREFIX):
            continue  # "Ticket Alert!" / "Watch live" reminders, not the match itself

        description = str(event.get("DESCRIPTION", ""))
        round_number = _parse_round_number(description) or _parse_round_number(summary)
        if round_number is None:
            result.ignored_out_of_range += 1
            continue
        if min_round is not None and round_number < min_round:
            result.ignored_out_of_range += 1
            continue
        if max_round is not None and round_number > max_round:
            result.ignored_out_of_range += 1
            continue

        home_name, away_name, time_tbc = _strip_match_summary(summary)
        if not home_name or not away_name:
            result.skipped.append((summary, "Could not split the event title into two teams"))
            continue

        if time_tbc:
            result.skipped.append((summary, "Kickoff time not yet confirmed by SPL (Time TBC)"))
            continue

        dtstart_prop = event.get("DTSTART")
        if dtstart_prop is None or not hasattr(dtstart_prop.dt, "astimezone"):
            result.skipped.append((summary, "Event has no usable start time"))
            continue

        home_club = _find_club(home_name, clubs_by_name)
        away_club = _find_club(away_name, clubs_by_name)
        if not home_club or not away_club:
            result.skipped.append((summary, f"Unrecognized club(s): {home_name!r} / {away_name!r}"))
            continue

        row = _build_row(
            dtstart_prop.dt, str(event.get("LOCATION", "")), round_number, home_club, away_club, competition,
            used_slugs,
        )
        used_slugs.add(row["slug"])
        result.rows.append(row)

        if dry_run:
            continue

        existing = (
            Match.objects.filter(competition=competition, round_number=round_number)
            .filter(Q(home_club=home_club, away_club=away_club) | Q(home_club=away_club, away_club=home_club))
            .first()
        )

        if existing:
            for field, value in row.items():
                if field == "slug":
                    continue  # never overwrite an existing match's slug - it may already be shared/published
                if field == "venue" and value is None:
                    continue  # don't blank out a previously-known venue just because the calendar's LOCATION is TBC this run
                setattr(existing, field, value)
            existing.save()
            result.updated += 1
        else:
            match = Match(**row)
            match.save()
            attach_default_checklist_items(match)
            result.created += 1

    return result
