# core/management/commands/backup_database.py
#
# `python manage.py backup_database` - creates a backup zip (db.sqlite3 +
# media/) under BASE_DIR/backups/, the same function the Control Panel's
# "Create Backup Now" button calls directly - matches
# sync_roshan_calendar.py's dual CLI/button pattern.
#
# Example Windows Task Scheduler action, run daily:
#   Program: D:\2025\webook-match-tracker\venv\Scripts\python.exe
#   Arguments: manage.py backup_database
#   Start in: D:\2025\webook-match-tracker\config

from django.core.management.base import BaseCommand

from core.backup import create_backup


class Command(BaseCommand):
    help = "Creates a full backup (database + media) under BASE_DIR/backups/."

    def handle(self, *args, **options):
        zip_path = create_backup()
        self.stdout.write(self.style.SUCCESS(f"Backup created: {zip_path}"))
