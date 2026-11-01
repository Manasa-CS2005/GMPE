import argparse
import logging
import os
import time
from datetime import datetime, time as datetime_time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from .database import make_engine, session_factory
from .mail import send_account_email
from .models import AccountProfile, AccountReminder, AccountTask, AccountUser
from .security import utc_now


LOGGER = logging.getLogger(__name__)
CLAIM_TIMEOUT = timedelta(minutes=15)
MAX_BATCH_SIZE = 100


def _validate_email_provider() -> None:
    mode = os.getenv("LIFELOG_EMAIL_BACKEND", "").strip().lower()
    if not mode:
        mode = "smtp" if os.getenv("LIFELOG_SMTP_HOST", "").strip() else "console"
    if mode == "console":
        raise ValueError(
            "The reminder worker does not send email to a real mailbox in console "
            "mode. Configure SMTP or Brevo in .env."
        )
    if mode == "brevo":
        if not os.getenv("LIFELOG_BREVO_API_KEY", "").strip():
            raise ValueError("Set LIFELOG_BREVO_API_KEY to send task reminders.")
        if not os.getenv("LIFELOG_SMTP_FROM_EMAIL", "").strip():
            raise ValueError("Set LIFELOG_SMTP_FROM_EMAIL to a verified sender.")
        return
    if mode == "smtp":
        if not os.getenv("LIFELOG_SMTP_HOST", "").strip():
            raise ValueError("Set LIFELOG_SMTP_HOST to send task reminders.")
        if not os.getenv("LIFELOG_SMTP_FROM_EMAIL", "").strip():
            raise ValueError("Set LIFELOG_SMTP_FROM_EMAIL to send task reminders.")
        return
    raise ValueError("LIFELOG_EMAIL_BACKEND must be 'smtp' or 'brevo' for reminders.")


def _scheduled_utc(due_date, reminder_time: str, timezone_name: str) -> datetime:
    try:
        tz = ZoneInfo(timezone_name)
        local_time = datetime_time.fromisoformat(reminder_time)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError("Invalid user reminder time or timezone.") from error
    local_datetime = datetime.combine(due_date, local_time, tzinfo=tz)
    return local_datetime.astimezone(timezone.utc).replace(tzinfo=None)


def _enqueue_due_reminders(session_factory_: sessionmaker, now: datetime) -> int:
    inserted = 0
    with session_factory_() as db:
        candidates = db.execute(
            select(AccountTask, AccountUser, AccountProfile)
            .join(AccountUser, AccountUser.id == AccountTask.user_id)
            .join(AccountProfile, AccountProfile.user_id == AccountUser.id)
            .where(
                AccountTask.completed.is_(False),
                AccountTask.reminder_enabled.is_(True),
                AccountTask.due_date.is_not(None),
                AccountTask.due_date <= now.date() + timedelta(days=2),
                AccountUser.email_verified.is_(True),
                AccountProfile.email_notifications.is_(True),
            )
        ).all()
        dialect = db.get_bind().dialect.name
        if dialect == "sqlite":
            insert_statement = sqlite_insert
        elif dialect == "postgresql":
            insert_statement = postgresql_insert
        else:
            raise RuntimeError(f"Unsupported reminder database dialect: {dialect}.")

        for task, _user, profile in candidates:
            try:
                scheduled_for = _scheduled_utc(
                    task.due_date,
                    profile.reminder_time,
                    profile.timezone,
                )
            except ValueError:
                LOGGER.error(
                    "Skipping reminder for task %s because its profile schedule is invalid.",
                    task.id,
                )
                continue
            if scheduled_for > now:
                continue
            statement = insert_statement(AccountReminder).values(
                task_id=task.id,
                scheduled_for=scheduled_for,
                status="pending",
                attempts=0,
                next_attempt_at=now,
                created_at=now,
            )
            statement = statement.on_conflict_do_nothing(
                index_elements=[
                    AccountReminder.task_id,
                    AccountReminder.scheduled_for,
                ]
            )
            result = db.execute(statement)
            inserted += result.rowcount or 0
        db.commit()
    return inserted


def _claim_reminders(session_factory_: sessionmaker, now: datetime) -> list[int]:
    with session_factory_() as db:
        db.execute(
            update(AccountReminder)
            .where(
                AccountReminder.status == "processing",
                AccountReminder.claimed_at < now - CLAIM_TIMEOUT,
            )
            .values(status="pending", claimed_at=None)
        )
        reminders = list(
            db.scalars(
                select(AccountReminder)
                .where(
                    AccountReminder.status == "pending",
                    AccountReminder.next_attempt_at <= now,
                )
                .order_by(AccountReminder.scheduled_for, AccountReminder.id)
                .limit(MAX_BATCH_SIZE)
                .with_for_update(skip_locked=True)
            )
        )
        claimed_ids = []
        for reminder in reminders:
            result = db.execute(
                update(AccountReminder)
                .where(
                    AccountReminder.id == reminder.id,
                    AccountReminder.status == "pending",
                )
                .values(
                    status="processing",
                    attempts=AccountReminder.attempts + 1,
                    claimed_at=now,
                )
            )
            if result.rowcount == 1:
                claimed_ids.append(reminder.id)
        db.commit()
    return claimed_ids


def _finish_reminder(
    session_factory_: sessionmaker,
    reminder_id: int,
    now: datetime,
    error: Exception | None = None,
) -> None:
    with session_factory_() as db:
        reminder = db.get(AccountReminder, reminder_id)
        if reminder is None:
            raise LookupError(f"Reminder {reminder_id} no longer exists.")
        reminder.claimed_at = None
        if error is None:
            reminder.status = "sent"
            reminder.sent_at = now
            reminder.last_error = None
        else:
            reminder.status = "pending"
            delay_minutes = min(5 * (2 ** min(reminder.attempts - 1, 16)), 360)
            reminder.next_attempt_at = now + timedelta(minutes=delay_minutes)
            reminder.last_error = type(error).__name__[:120]
        db.commit()


def run_reminder_cycle(
    session_factory_: sessionmaker,
    email_sender=send_account_email,
    now: datetime | None = None,
) -> dict[str, int]:
    now = now or utc_now()
    queued = _enqueue_due_reminders(session_factory_, now)
    claimed_ids = _claim_reminders(session_factory_, now)
    sent = 0
    failed = 0
    for reminder_id in claimed_ids:
        with session_factory_() as db:
            reminder = db.get(AccountReminder, reminder_id)
            if reminder is None:
                raise LookupError(f"Reminder {reminder_id} no longer exists.")
            task = db.get(AccountTask, reminder.task_id)
            user = db.get(AccountUser, task.user_id) if task is not None else None
            profile = (
                db.get(AccountProfile, user.id)
                if user is not None
                else None
            )
            still_eligible = (
                task is not None
                and user is not None
                and profile is not None
                and not task.completed
                and task.reminder_enabled
                and task.due_date is not None
                and task.due_date == reminder.scheduled_for.date()
                and user.email_verified
                and profile.email_notifications
            )
            title = task.title if task is not None else ""
            due_date = task.due_date.isoformat() if still_eligible else ""
            recipient = user.email if still_eligible and user is not None else ""
        if not still_eligible:
            with session_factory_() as db:
                queued_reminder = db.get(AccountReminder, reminder_id)
                if queued_reminder is not None:
                    queued_reminder.status = "cancelled"
                    queued_reminder.claimed_at = None
                    db.commit()
            continue
        try:
            email_sender(
                recipient,
                f"LifeLog AI task reminder: {title}",
                f"This is a reminder for your LifeLog AI task:\n\n"
                f"{title}\nDue date: {due_date}\n\n"
                "You can review and update this task in your LifeLog AI account.",
            )
        except Exception as error:
            _finish_reminder(session_factory_, reminder_id, now, error)
            LOGGER.error(
                "Reminder %s delivery failed (%s); retry scheduled.",
                reminder_id,
                type(error).__name__,
            )
            failed += 1
            continue
        _finish_reminder(session_factory_, reminder_id, now)
        sent += 1
    return {"queued": queued, "sent": sent, "failed": failed}


def run_worker(
    session_factory_: sessionmaker,
    interval_seconds: int = 60,
    once: bool = False,
) -> None:
    if interval_seconds < 1:
        raise ValueError("The worker interval must be at least one second.")
    _validate_email_provider()
    while True:
        result = run_reminder_cycle(session_factory_)
        if result["queued"] or result["sent"] or result["failed"]:
            LOGGER.info(
                "Account reminder cycle: %s queued, %s sent, %s failed.",
                result["queued"],
                result["sent"],
                result["failed"],
            )
        if once:
            return
        time.sleep(interval_seconds)


def main() -> None:
    from dotenv import load_dotenv

    parser = argparse.ArgumentParser(
        description="Deliver reminders for authenticated LifeLog AI tasks."
    )
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument(
        "--once",
        action="store_true",
        help="Send due reminders once and exit.",
    )
    arguments = parser.parse_args()
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    engine: Engine = make_engine()
    try:
        run_worker(
            session_factory(engine),
            interval_seconds=arguments.interval,
            once=arguments.once,
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
