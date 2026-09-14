import shutil
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from django.test import override_settings

from core import backup as backup_module
from core.backup import BackupError, create_backup, list_backups, restore_backup


def _make_sqlite_file(path, *, valid=True):
    if valid:
        conn = sqlite3.connect(str(path))
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO t (name) VALUES ('hello')")
        conn.commit()
        conn.close()
    else:
        path.write_bytes(b"not a real sqlite file")


class BackupRestoreTests(unittest.TestCase):
    """Pure filesystem tests against a temp "fake project" (its own
    db.sqlite3 + media/ + backups/), isolated from both the real dev
    database and Django's own test-database machinery (which swaps sqlite
    to :memory: during `manage.py test`, incompatible with testing actual
    file backup/restore) - core.backup's module-level paths are patched to
    point at the temp dir for the duration of each test."""

    def setUp(self):
        self.tmp_root = Path(tempfile.mkdtemp(prefix="backup_test_"))
        self.db_path = self.tmp_root / "db.sqlite3"
        self.media_root = self.tmp_root / "media"
        self.backups_dir = self.tmp_root / "backups"
        self.media_root.mkdir()
        (self.media_root / "logos").mkdir()
        (self.media_root / "logos" / "club.png").write_bytes(b"fake-image-bytes")
        _make_sqlite_file(self.db_path)

        override = override_settings(
            MEDIA_ROOT=self.media_root,
            DATABASES={"default": {"NAME": str(self.db_path)}},
        )
        override.enable()
        self.addCleanup(override.disable)

        backups_dir_patch = mock.patch.object(backup_module, "BACKUPS_DIR", self.backups_dir)
        backups_dir_patch.start()
        self.addCleanup(backups_dir_patch.stop)

    def tearDown(self):
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def test_create_backup_produces_zip_with_db_and_media(self):
        zip_path = create_backup()
        self.assertTrue(zip_path.exists())
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            self.assertIn("db.sqlite3", names)
            self.assertIn("media/logos/club.png", names)

    def test_list_backups_returns_newest_first(self):
        first = create_backup(label="one")
        second = create_backup(label="two")
        listed = list_backups()
        self.assertEqual([b["path"] for b in listed][:2], [second, first])

    def test_restore_replaces_db_and_media_and_takes_safety_backup(self):
        # Build a second, distinct "incoming" backup to restore from.
        other_root = Path(tempfile.mkdtemp(prefix="backup_test_other_"))
        self.addCleanup(shutil.rmtree, other_root, ignore_errors=True)
        other_db = other_root / "db.sqlite3"
        _make_sqlite_file(other_db)
        conn = sqlite3.connect(str(other_db))
        conn.execute("INSERT INTO t (name) VALUES ('from-the-restored-backup')")
        conn.commit()
        conn.close()

        incoming_zip = other_root / "incoming.zip"
        with zipfile.ZipFile(incoming_zip, "w") as zf:
            zf.write(other_db, "db.sqlite3")
            zf.writestr("media/logos/other-club.png", b"other-fake-bytes")

        backups_before = len(list_backups())
        with open(incoming_zip, "rb") as f:
            safety_backup_path = restore_backup(f)

        # A safety backup of the pre-restore state was taken.
        self.assertTrue(safety_backup_path.exists())
        self.assertEqual(len(list_backups()), backups_before + 1)

        # The live db now has the restored content, not the original.
        conn = sqlite3.connect(str(self.db_path))
        rows = conn.execute("SELECT name FROM t").fetchall()
        conn.close()
        self.assertIn(("from-the-restored-backup",), rows)

        # The live media now has the restored file, not the original.
        self.assertTrue((self.media_root / "logos" / "other-club.png").exists())
        self.assertFalse((self.media_root / "logos" / "club.png").exists())

    def test_restore_rejects_zip_without_db_file(self):
        bad_zip = self.tmp_root / "bad.zip"
        with zipfile.ZipFile(bad_zip, "w") as zf:
            zf.writestr("readme.txt", b"no db in here")

        with open(bad_zip, "rb") as f:
            with self.assertRaises(BackupError):
                restore_backup(f)

        # Nothing live was touched.
        conn = sqlite3.connect(str(self.db_path))
        rows = conn.execute("SELECT name FROM t").fetchall()
        conn.close()
        self.assertEqual(rows, [("hello",)])

    def test_restore_rejects_corrupt_database_file(self):
        bad_zip = self.tmp_root / "corrupt.zip"
        with zipfile.ZipFile(bad_zip, "w") as zf:
            zf.writestr("db.sqlite3", b"this is not a sqlite database")

        with open(bad_zip, "rb") as f:
            with self.assertRaises(BackupError):
                restore_backup(f)

        conn = sqlite3.connect(str(self.db_path))
        rows = conn.execute("SELECT name FROM t").fetchall()
        conn.close()
        self.assertEqual(rows, [("hello",)])
