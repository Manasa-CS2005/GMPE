import io
import json
import sqlite3
import tempfile
import unittest
import zipfile
from contextlib import closing
from pathlib import Path

from data_management import (
    delete_memory,
    delete_user_account,
    export_user_archive,
    update_memory,
)


class DataManagementTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.db_path = self.root / "lifelog.db"
        self.assets_root = self.root / "lifelog_assets"
        self.assets_root.mkdir()
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.executescript(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE profiles (
                    user_id INTEGER PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    writing_style TEXT NOT NULL,
                    journal_tone TEXT NOT NULL,
                    interests TEXT NOT NULL,
                    reminder_time TEXT NOT NULL
                );
                CREATE TABLE memories (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    source_text TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    title TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    memory_date TEXT NOT NULL
                );
                CREATE TABLE tasks (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    memory_id INTEGER,
                    title TEXT NOT NULL,
                    completed INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    due_date TEXT,
                    priority TEXT NOT NULL,
                    reminder_enabled INTEGER NOT NULL
                );
                CREATE TABLE reminder_deliveries (
                    id INTEGER PRIMARY KEY,
                    task_id INTEGER NOT NULL,
                    due_date TEXT NOT NULL
                );
                CREATE TABLE assets (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    memory_id INTEGER,
                    original_name TEXT NOT NULL,
                    stored_name TEXT NOT NULL,
                    asset_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    extracted_text TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                INSERT INTO users VALUES (1, 'Alex', 'alex@example.com', '2026-01-01');
                INSERT INTO users VALUES (2, 'Sam', 'sam@example.com', '2026-01-02');
                INSERT INTO profiles VALUES (1, 'Alex', 'Reflective', 'Warm', '', '09:00');
                INSERT INTO memories VALUES
                    (1, 1, '2026-01-01', 'source', 'Simple Journal',
                     '{"journal":"entry"}', 'Title', 'tag', '2026-01-01');
                INSERT INTO memories VALUES
                    (2, 2, '2026-01-02', 'private', 'Simple Journal',
                     '{"journal":"private"}', 'Other', '', '2026-01-02');
                INSERT INTO tasks VALUES
                    (1, 1, 1, 'Task', 0, '2026-01-01', NULL, 'Normal', 0);
                INSERT INTO reminder_deliveries VALUES (1, 1, '2026-01-01');
                INSERT INTO assets VALUES
                    (1, 1, 1, 'note.txt', 'stored.txt', 'document', 4,
                     'processed', 'text', '2026-01-01');
                """
            )
        self.user_asset_dir = self.assets_root / "1"
        self.user_asset_dir.mkdir()
        (self.user_asset_dir / "stored.txt").write_text("data", encoding="utf-8")

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_update_memory_is_scoped_to_owner(self):
        self.assertFalse(
            update_memory(
                self.db_path, 2, 1, "Changed", "", "2026-01-03", "new", {"journal": "new"}
            )
        )
        self.assertTrue(
            update_memory(
                self.db_path, 1, 1, " Changed ", " memories ", "2026-01-03",
                " updated source ", {"journal": "updated"},
            )
        )
        with closing(sqlite3.connect(self.db_path)) as connection:
            row = connection.execute(
                "SELECT title, tags, source_text, result_json FROM memories WHERE id = 1"
            ).fetchone()
        self.assertEqual(row[:3], ("Changed", "memories", "updated source"))
        self.assertEqual(json.loads(row[3]), {"journal": "updated"})

    def test_export_contains_only_account_data_and_attached_files(self):
        exported = export_user_archive(self.db_path, self.assets_root, 1)
        with zipfile.ZipFile(io_bytes(exported)) as archive:
            payload = json.loads(archive.read("lifelog-export.json"))
            self.assertEqual(payload["account"]["email"], "alex@example.com")
            self.assertEqual([item["id"] for item in payload["memories"]], [1])
            self.assertNotIn("password_hash", payload["account"])
            self.assertEqual(archive.read("assets/1_note.txt"), b"data")

    def test_delete_memory_removes_linked_data_and_file(self):
        self.assertFalse(delete_memory(self.db_path, self.assets_root, 2, 1))
        self.assertTrue(delete_memory(self.db_path, self.assets_root, 1, 1))
        self.assertFalse((self.user_asset_dir / "stored.txt").exists())
        with closing(sqlite3.connect(self.db_path)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM memories WHERE id = 1").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM tasks WHERE memory_id = 1").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM reminder_deliveries WHERE task_id = 1").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM assets WHERE memory_id = 1").fetchone()[0], 0)

    def test_delete_account_removes_owned_rows_and_files(self):
        self.assertTrue(delete_user_account(self.db_path, self.assets_root, 1))
        with closing(sqlite3.connect(self.db_path)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM users WHERE id = 1").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM users WHERE id = 2").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM memories WHERE user_id = 1").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM reminder_deliveries WHERE task_id = 1").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT id FROM memories").fetchall(), [(2,)])
        self.assertFalse((self.user_asset_dir / "stored.txt").exists())

    def test_export_fails_for_missing_original_file(self):
        (self.user_asset_dir / "stored.txt").unlink()
        with self.assertRaises(FileNotFoundError):
            export_user_archive(self.db_path, self.assets_root, 1)


def io_bytes(value):
    return io.BytesIO(value)


if __name__ == "__main__":
    unittest.main()
