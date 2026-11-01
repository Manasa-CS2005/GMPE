import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import select

from backend.database import Base, make_engine, session_factory
from backend.models import (
    AccountProfile,
    AccountReminder,
    AccountTask,
    AccountUser,
)
from backend.reminder_worker import _validate_email_provider, run_reminder_cycle


class AccountReminderTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "reminders.sqlite"
        self.engine = make_engine(f"sqlite:///{database_path.as_posix()}")
        Base.metadata.create_all(self.engine)
        self.session_maker = session_factory(self.engine)
        with self.session_maker() as db:
            user = AccountUser(
                full_name="Alex Morgan",
                email="alex@example.com",
                password_hash="not-used",
                email_verified=True,
                created_at=datetime(2026, 10, 1),
            )
            db.add(user)
            db.flush()
            db.add(
                AccountProfile(
                    user_id=user.id,
                    timezone="Asia/Kolkata",
                    reminder_time="09:00",
                    email_notifications=True,
                    in_app_notifications=True,
                )
            )
            db.add(
                AccountTask(
                    user_id=user.id,
                    title="Finish the report",
                    description="",
                    due_date=date(2026, 10, 30),
                    priority="normal",
                    completed=False,
                    reminder_enabled=True,
                    created_at=datetime(2026, 10, 1),
                    updated_at=datetime(2026, 10, 1),
                )
            )
            db.commit()
        self.now = datetime(2026, 10, 30, 4, 0)

    def tearDown(self):
        self.engine.dispose()
        self.temporary_directory.cleanup()

    def test_timezone_scheduled_email_is_persistent_and_not_duplicated(self):
        sent = []
        first = run_reminder_cycle(
            self.session_maker,
            email_sender=lambda *message: sent.append(message),
            now=self.now,
        )
        self.assertEqual(first, {"queued": 1, "sent": 1, "failed": 0})
        self.assertEqual(len(sent), 1)
        self.assertIn("Finish the report", sent[0][2])
        with self.session_maker() as db:
            reminder = db.scalar(select(AccountReminder))
            self.assertEqual(reminder.status, "sent")
            self.assertEqual(reminder.scheduled_for, datetime(2026, 10, 30, 3, 30))

        second = run_reminder_cycle(
            self.session_maker,
            email_sender=lambda *message: sent.append(message),
            now=self.now,
        )
        self.assertEqual(second, {"queued": 0, "sent": 0, "failed": 0})
        self.assertEqual(len(sent), 1)

    def test_failed_email_is_retried_with_backoff(self):
        def fail_delivery(*_message):
            raise RuntimeError("provider unavailable")

        first = run_reminder_cycle(
            self.session_maker,
            email_sender=fail_delivery,
            now=self.now,
        )
        self.assertEqual(first, {"queued": 1, "sent": 0, "failed": 1})
        with self.session_maker() as db:
            reminder = db.scalar(select(AccountReminder))
            self.assertEqual(reminder.status, "pending")
            self.assertEqual(reminder.attempts, 1)
            self.assertEqual(reminder.next_attempt_at, datetime(2026, 10, 30, 4, 5))

        sent = []
        retried = run_reminder_cycle(
            self.session_maker,
            email_sender=lambda *message: sent.append(message),
            now=datetime(2026, 10, 30, 4, 6),
        )
        self.assertEqual(retried, {"queued": 0, "sent": 1, "failed": 0})
        self.assertEqual(len(sent), 1)

    def test_worker_refuses_console_mail_mode(self):
        with patch.dict(
            "os.environ",
            {"LIFELOG_EMAIL_BACKEND": "console"},
            clear=False,
        ):
            with self.assertRaisesRegex(ValueError, "does not send email"):
                _validate_email_provider()


if __name__ == "__main__":
    unittest.main()
