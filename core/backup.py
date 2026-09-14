# core/backup.py
#
# Full database + media backup/restore - the single most destructive
# feature in this codebase (a restore replaces the live db.sqlite3 and the
# entire media/ folder), so every step here is deliberately conservative:
# validate before touching anything live, and always take a fresh safety
# backup of the current state before a restore, even though the caller may
# already have one.
#
# No backup metadata is stored in the database itself - that would create a
# chicken-and-egg problem (the very table describing backups would be wiped
# out by a restore). Backups are plain timestamped .zip files under
# BASE_DIR/backups/, each containing db.sqlite3 plus the whole media/ tree.

import shutil
import sqlite3
import tempfile
import time
import zipfile
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.db import connections
from django.utils import timezone

BACKUPS_DIR = settings.BASE_DIR / "backups"
DB_NAME_IN_ZIP = "db.sqlite3"
MEDIA_PREFIX_IN_ZIP = "media/"


class BackupError(Exception):
    pass


def _db_path():
    return Path(settings.DATABASES["default"]["NAME"])


def _timestamp():
    return timezone.localtime().strftime("%Y%m%d-%H%M%S")


def create_backup(*, label=None):
    """Zips the live db.sqlite3 + media/ into BACKUPS_DIR. `label`, if given,
    is appended to the filename (e.g. "auto-before-restore") so a safety
    backup taken automatically during a restore is distinguishable from one
    a Super Admin asked for on purpose."""
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    suffix = f"-{label}" if label else ""
    filename = f"backup-{_timestamp()}{suffix}.zip"
    zip_path = BACKUPS_DIR / filename

    db_path = _db_path()
    if not db_path.exists():
        raise BackupError(f"Database file not found: {db_path}")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(db_path, DB_NAME_IN_ZIP)
        media_root = Path(settings.MEDIA_ROOT)
        if media_root.exists():
            for file_path in media_root.rglob("*"):
                if file_path.is_file():
                    zf.write(file_path, MEDIA_PREFIX_IN_ZIP + str(file_path.relative_to(media_root)).replace("\\", "/"))

    return zip_path


def list_backups():
    """Every backup-*.zip under BACKUPS_DIR, newest first, as
    {name, path, size, created_at}."""
    if not BACKUPS_DIR.exists():
        return []
    entries = []
    for path in BACKUPS_DIR.glob("backup-*.zip"):
        stat = path.stat()
        naive_mtime = datetime.fromtimestamp(stat.st_mtime)
        entries.append({
            "name": path.name,
            "path": path,
            "size": stat.st_size,
            "created_at": timezone.make_aware(naive_mtime),
        })
    entries.sort(key=lambda e: e["created_at"], reverse=True)
    return entries


def _rename_with_retry(src, dst, attempts=8, delay=0.5):
    """Path.rename(), retrying on PermissionError - on Windows, a directory
    freshly written by zipfile.extractall() (or one about to be moved aside)
    can be transiently locked for a moment by Windows Defender's real-time
    scan or the search indexer, which surfaces as WinError 5 (Access is
    denied) even though nothing in the app itself holds the file open. Seen
    live during this feature's own manual restore walkthrough - a plain,
    unretried rename() failed here on a real Windows dev machine."""
    last_error = None
    for attempt in range(attempts):
        try:
            src.rename(dst)
            return
        except PermissionError as exc:
            last_error = exc
            time.sleep(delay)
    raise last_error


def _validate_zip_and_extract(zip_file_like, extract_dir):
    """Opens the zip, extracts it into extract_dir, and confirms the
    extracted db.sqlite3 opens and passes PRAGMA integrity_check - all
    BEFORE anything live is touched. Raises BackupError on any problem."""
    try:
        with zipfile.ZipFile(zip_file_like) as zf:
            names = zf.namelist()
            if DB_NAME_IN_ZIP not in names:
                raise BackupError(f"This file doesn't look like a valid backup (no {DB_NAME_IN_ZIP} inside).")
            zf.extractall(extract_dir)
    except zipfile.BadZipFile:
        raise BackupError("This file isn't a valid .zip archive.")

    extracted_db = Path(extract_dir) / DB_NAME_IN_ZIP
    try:
        conn = sqlite3.connect(str(extracted_db))
        try:
            result = conn.execute("PRAGMA integrity_check").fetchone()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        raise BackupError(f"The backup's database file failed to open: {exc}")

    if not result or result[0] != "ok":
        raise BackupError(f"The backup's database file failed integrity_check: {result}")

    return extracted_db


def restore_backup(zip_file_like):
    """The restore procedure, in order:
    1. Auto-backup the CURRENT live db+media first, unconditionally.
    2. Extract the target zip to a temp dir and validate its db.sqlite3
       (integrity_check) BEFORE touching anything live.
    3. Close all DB connections.
    4. Atomically replace db.sqlite3 (os.replace) and swap in the extracted
       media/ folder.
    Returns the safety backup's path, so the caller can tell the operator
    exactly where the pre-restore state was captured."""
    safety_backup_path = create_backup(label="auto-before-restore")

    # Extracted under BACKUPS_DIR (same drive/filesystem as db.sqlite3 and
    # media/) rather than the OS default temp dir, so the file/directory
    # replacement below is a same-volume move, not a slow (and on some
    # platforms unsupported) cross-device one.
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="restore-", dir=BACKUPS_DIR) as extract_dir:
        extracted_db = _validate_zip_and_extract(zip_file_like, extract_dir)

        connections.close_all()

        live_db_path = _db_path()
        live_db_path.parent.mkdir(parents=True, exist_ok=True)
        extracted_db.replace(live_db_path)

        extracted_media = Path(extract_dir) / "media"
        media_root = Path(settings.MEDIA_ROOT)
        if extracted_media.exists():
            old_media_aside = media_root.with_name(media_root.name + f".pre-restore-{_timestamp()}")
            moved_old_media_aside = False
            if media_root.exists():
                _rename_with_retry(media_root, old_media_aside)
                moved_old_media_aside = True
            try:
                _rename_with_retry(extracted_media, media_root)
            except PermissionError:
                # Roll back so the live media/ folder is never left missing -
                # the db.sqlite3 swap above has already happened and stays,
                # but media/ must not end up in a half-swapped state.
                if moved_old_media_aside:
                    old_media_aside.rename(media_root)
                raise BackupError(
                    "The database was restored, but swapping in the restored media files failed "
                    "(Windows file lock). The previous media files were kept in place - please retry the restore."
                )
            if old_media_aside.exists():
                shutil.rmtree(old_media_aside, ignore_errors=True)

    return safety_backup_path
