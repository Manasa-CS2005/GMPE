import os
import smtplib
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from reminders import (
    SMTPConfig,
    run_reminder_cycle,
    smtp_config_from_environment,
)


class FakeSMTP:
    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.messages = []
        self.tls_started = False
        self.logged_in = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def starttls(self):
        self.tls_started = True

    def login(self, username, password):
        self.logged_in = True

    def send_message(self, message):
        self.messages.append(message)
        return {}


class ReminderTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temporary_directory.name) / "lifelog.db"
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.executescript(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL
                );
                CREATE TABLE profiles (
                    user_id INTEGER PRIMARY KEY,
                    reminder_time TEXT NOT NULL
                );
                CREATE TABLE tasks (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    completed INTEGER NOT NULL DEFAULT 0,
                    due_date TEXT,
                    reminder_enabled INTEGER NOT NULL DEFAULT 0
                );
                INSERT INTO users VALUES (1, 'Alex', 'alex@example.com');
                INSERT INTO profiles VALUES (1, '09:00');
                INSERT INTO tasks VALUES (1, 1, 'Submit assignment', 0, '2026-10-29', 1);
                INSERT INTO tasks VALUES (2, 1, 'Buy groceries', 0, '2026-10-29', 0);
                INSERT INTO tasks VALUES (3, 1, 'Finished task', 1, '2026-10-29', 1);
                INSERT INTO tasks VALUES (4, 1, 'No due date', 0, NULL, 1);
                """
            )
        self.config = SMTPConfig(
            host="smtp.example.com",
            port=587,
            from_email="reminders@example.com",
            username="smtp-user",
            password="smtp-password",
            use_ssl=False,
            use_starttls=True,
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_only_due_opted_in_pending_tasks_are_sent_once(self):
        smtp_instances = []

        def smtp_factory(*args, **kwargs):
            instance = FakeSMTP(*args, **kwargs)
            smtp_instances.append(instance)
            return instance

        before_preferred_time = datetime(2026, 10, 29, 8, 59)
        result = run_reminder_cycle(
            self.db_path,
            self.config,
            now=before_preferred_time,
            smtp_factory=smtp_factory,
        )
        self.assertEqual(result, {"sent": 0, "failed": 0})

        now = datetime(2026, 10, 29, 9, 0)
        result = run_reminder_cycle(
            self.db_path, self.config, now=now, smtp_factory=smtp_factory
        )
        self.assertEqual(result, {"sent": 1, "failed": 0})
        self.assertEqual(len(smtp_instances), 1)
        self.assertEqual(smtp_instances[0].messages[0]["To"], "alex@example.com")
        self.assertIn("Submit assignment", smtp_instances[0].messages[0].get_content())
        self.assertTrue(smtp_instances[0].tls_started)
        self.assertTrue(smtp_instances[0].logged_in)

        duplicate = run_reminder_cycle(
            self.db_path, self.config, now=now, smtp_factory=smtp_factory
        )
        self.assertEqual(duplicate, {"sent": 0, "failed": 0})
        with closing(sqlite3.connect(self.db_path)) as connection:
            statuses = connection.execute(
                "SELECT task_id, status FROM reminder_deliveries ORDER BY task_id"
            ).fetchall()
        self.assertEqual(statuses, [(1, "sent")])

    def test_smtp_failure_is_persisted_and_retried_after_backoff(self):
        def failing_factory(*args, **kwargs):
            raise smtplib.SMTPConnectError(421, b"temporarily unavailable")

        now = datetime(2026, 10, 29, 9, 0)
        result = run_reminder_cycle(
            self.db_path, self.config, now=now, smtp_factory=failing_factory
        )
        self.assertEqual(result, {"sent": 0, "failed": 1})
        with closing(sqlite3.connect(self.db_path)) as connection:
            delivery = connection.execute(
                "SELECT status, attempts, next_attempt_at, last_error "
                "FROM reminder_deliveries WHERE task_id = 1"
            ).fetchone()
        self.assertEqual(delivery, (
            "pending",
            1,
            (now + timedelta(minutes=5)).isoformat(timespec="seconds"),
            "SMTP status 421: temporarily unavailable",
        ))

        before_retry = run_reminder_cycle(
            self.db_path,
            self.config,
            now=now + timedelta(minutes=4),
            smtp_factory=FakeSMTP,
        )
        self.assertEqual(before_retry, {"sent": 0, "failed": 0})
        after_retry = run_reminder_cycle(
            self.db_path,
            self.config,
            now=now + timedelta(minutes=5),
            smtp_factory=FakeSMTP,
        )
        self.assertEqual(after_retry, {"sent": 1, "failed": 0})

    def test_worker_configuration_requires_valid_smtp_values(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "LIFELOG_SMTP_HOST"):
                smtp_config_from_environment()

        environment = {
            "LIFELOG_SMTP_HOST": "smtp.example.com",
            "LIFELOG_SMTP_FROM_EMAIL": "reminders@example.com",
            "LIFELOG_SMTP_USE_SSL": "true",
            "LIFELOG_SMTP_USE_STARTTLS": "true",
        }
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaisesRegex(ValueError, "Enable only one"):
                smtp_config_from_environment()


if __name__ == "__main__":
    unittest.main()
