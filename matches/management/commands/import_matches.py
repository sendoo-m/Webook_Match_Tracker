from datetime import datetime
from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand, CommandError

from matches.models import Club, Venue, Match


class Command(BaseCommand):
    help = "Import matches from Excel workbook"

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            required=True,
            help="Path to Excel file",
        )

    def handle(self, *args, **options):
        file_path = Path(options["file"])

        if not file_path.exists():
            raise CommandError(f"File not found: {file_path}")

        sheets = pd.read_excel(file_path, sheet_name=None, header=None)

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for sheet_name, df in sheets.items():
            if df.empty:
                continue

            df = df.dropna(how="all").reset_index(drop=True)

            if len(df.index) <= 3:
                continue

            data_rows = df.iloc[3:].reset_index(drop=True)

            for _, row in data_rows.iterrows():
                round_number = self.to_int(row.iloc[0] if len(row) > 0 else None)
                title_en = self.clean(row.iloc[1] if len(row) > 1 else None)
                title_ar = self.clean(row.iloc[2] if len(row) > 2 else None)
                description_en = self.clean(row.iloc[3] if len(row) > 3 else None)
                description_ar = self.clean(row.iloc[4] if len(row) > 4 else None)
                sale_launch_time = self.parse_time(row.iloc[5] if len(row) > 5 else None)
                sale_launch_date = self.parse_date(row.iloc[6] if len(row) > 6 else None)
                event_date = self.parse_date(row.iloc[7] if len(row) > 7 else None)
                gates_open_time = self.parse_time(row.iloc[9] if len(row) > 9 else None)
                match_start_time = self.parse_time(row.iloc[10] if len(row) > 10 else None)
                match_end_time = self.parse_time(row.iloc[11] if len(row) > 11 else None)
                venue_en = self.clean(row.iloc[14] if len(row) > 14 else None)
                venue_ar = self.clean(row.iloc[15] if len(row) > 15 else None)
                google_maps_url = self.clean(row.iloc[16] if len(row) > 16 else None)
                slug = self.clean(row.iloc[17] if len(row) > 17 else None)

                if not title_en or not title_ar or not slug:
                    skipped_count += 1
                    continue

                clubs = self.extract_clubs_from_title(title_en)
                if not clubs:
                    skipped_count += 1
                    continue

                home_name_en, away_name_en = clubs

                home_club, _ = Club.objects.get_or_create(
                    name_en=home_name_en,
                    defaults={
                        "name_ar": home_name_en,
                        "short_name_en": home_name_en,
                        "short_name_ar": home_name_en,
                    },
                )

                away_club, _ = Club.objects.get_or_create(
                    name_en=away_name_en,
                    defaults={
                        "name_ar": away_name_en,
                        "short_name_en": away_name_en,
                        "short_name_ar": away_name_en,
                    },
                )

                venue = None
                if venue_en or venue_ar:
                    venue, _ = Venue.objects.update_or_create(
                        name_en=venue_en or venue_ar or "Unknown Venue",
                        defaults={
                            "name_ar": venue_ar or venue_en or "ملعب غير معروف",
                            "google_maps_url": google_maps_url or "",
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
                        "sale_launch_date": sale_launch_date,
                        "sale_launch_time": sale_launch_time,
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
        try:
            return pd.to_datetime(value).date()
        except Exception:
            return None

    def parse_time(self, value):
        if pd.isna(value):
            return None

        if isinstance(value, datetime):
            return value.time()

        value = str(value).strip()
        if not value or value.upper() == "TBC":
            return None

        for fmt in ("%I:%M %p", "%H:%M", "%H:%M:%S"):
            try:
                return datetime.strptime(value, fmt).time()
            except ValueError:
                continue

        return None

    def extract_clubs_from_title(self, title):
        if " - " in title:
            title = title.split(" - ", 1)[1].strip()

        if " vs " not in title:
            return None

        parts = title.split(" vs ")
        if len(parts) != 2:
            return None

        home = parts[0].strip()
        away = parts[1].strip()
        return home, away