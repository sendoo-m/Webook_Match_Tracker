from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from django.core.management.base import BaseCommand, CommandError

from matches.models import Club, Match, Venue

RIYADH_TZ = ZoneInfo("Asia/Riyadh")

# Maps a name as it appears in the workbook to the existing Club.name_en it
# actually corresponds to, for names that don't match exactly.
CLUB_NAME_ALIASES = {
    "Al Diriyah Club": "Al Diriyah",
}


class Command(BaseCommand):
    help = "Import matches from the per-club RSL workbook (one sheet per club, single header row)."

    def add_arguments(self, parser):
        parser.add_argument("--file", type=str, required=True, help="Path to the Excel workbook")
        parser.add_argument(
            "--sheets",
            type=str,
            default="",
            help="Comma-separated sheet names to import (default: all sheets in the file)",
        )

    def handle(self, *args, **options):
        file_path = Path(options["file"])
        if not file_path.exists():
            raise CommandError(f"File not found: {file_path}")

        sheet_filter = [s.strip() for s in options["sheets"].split(",") if s.strip()]
        sheets = pd.read_excel(file_path, sheet_name=None, header=None)

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for sheet_name, df in sheets.items():
            if sheet_filter and sheet_name not in sheet_filter:
                continue

            data_rows = df.iloc[1:]

            for _, row in data_rows.iterrows():
                round_number = self.to_int(row.iloc[0])
                title_ar = self.clean(row.iloc[1])
                title_en = self.clean(row.iloc[2])
                description_ar = self.clean(row.iloc[3])
                description_en = self.clean(row.iloc[4])
                event_date = self.parse_date(row.iloc[5])
                match_start_time = self.parse_time(row.iloc[6])
                sale_starts_at = self.parse_datetime(row.iloc[7])
                gates_open_time = self.parse_time(row.iloc[8])
                match_end_time = self.parse_time(row.iloc[9])
                venue_ar = self.clean(row.iloc[10])
                venue_en = self.clean(row.iloc[11])
                google_maps_url = self.clean(row.iloc[12])
                slug = self.clean(row.iloc[13])

                if not title_en or not title_ar or not slug:
                    skipped_count += 1
                    continue

                clubs = self.extract_clubs_from_title(title_en)
                if not clubs:
                    skipped_count += 1
                    continue

                home_name_en, away_name_en = clubs
                home_name_en = CLUB_NAME_ALIASES.get(home_name_en, home_name_en)
                away_name_en = CLUB_NAME_ALIASES.get(away_name_en, away_name_en)

                try:
                    home_club = Club.objects.get(name_en=home_name_en)
                    away_club = Club.objects.get(name_en=away_name_en)
                except Club.DoesNotExist as exc:
                    self.stdout.write(self.style.WARNING(
                        f"Skipping {slug}: club not found ({exc})"
                    ))
                    skipped_count += 1
                    continue

                venue = None
                if venue_en or venue_ar:
                    venue, _ = Venue.objects.update_or_create(
                        name_en=venue_en or venue_ar,
                        defaults={
                            "name_ar": venue_ar or venue_en,
                            "google_maps_url": google_maps_url,
                        },
                    )

                _, created = Match.objects.update_or_create(
                    slug=slug,
                    defaults={
                        "round_number": round_number,
                        "home_club": home_club,
                        "away_club": away_club,
                        "venue": venue,
                        "title_en": title_en,
                        "title_ar": title_ar,
                        "description_en": description_en,
                        "description_ar": description_ar,
                        "sale_starts_at": sale_starts_at,
                        "event_date": event_date,
                        "gates_open_time": gates_open_time,
                        "match_start_time": match_start_time,
                        "match_end_time": match_end_time,
                    },
                )

                if created:
                    created_count += 1
                else:
                    updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Import completed. Created: {created_count}, Updated: {updated_count}, Skipped: {skipped_count}"
            )
        )

    def clean(self, value):
        if pd.isna(value):
            return ""
        value = str(value).strip()
        if value.upper() == "TBC":
            return ""
        return value

    def to_int(self, value):
        if pd.isna(value):
            return None
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None

    def parse_date(self, value):
        if pd.isna(value):
            return None
        if isinstance(value, datetime):
            return value.date()
        value = str(value).strip()
        if not value or value.upper() == "TBC":
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None

    def parse_time(self, value):
        if pd.isna(value):
            return None
        if isinstance(value, datetime):
            return value.time()
        value = str(value).strip()
        if not value or value.upper() == "TBC":
            return None
        for fmt in ("%H:%M", "%I:%M %p", "%H:%M:%S"):
            try:
                return datetime.strptime(value, fmt).time()
            except ValueError:
                continue
        return None

    def parse_datetime(self, value):
        if pd.isna(value):
            return None
        if isinstance(value, datetime):
            naive = value
        else:
            value = str(value).strip()
            if not value or value.upper() == "TBC":
                return None
            naive = None
            for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
                try:
                    naive = datetime.strptime(value, fmt)
                    break
                except ValueError:
                    continue
            if naive is None:
                return None
        return naive.replace(tzinfo=RIYADH_TZ)

    def extract_clubs_from_title(self, title):
        if " - " in title:
            title = title.split(" - ", 1)[1].strip()
        if " vs " not in title:
            return None
        parts = title.split(" vs ")
        if len(parts) != 2:
            return None
        return parts[0].strip(), parts[1].strip()