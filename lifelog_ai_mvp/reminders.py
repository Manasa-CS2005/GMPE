import logging
import os
import smtplib
import sqlite3
import time
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path


LOGGER = logging.getLogger(__name__)
CLAIM_TIMEOUT = timedelta(minutes=15)


@contextmanager
def _connect(db_path, timeout=5):
    with closing(sqlite3.connect(db_path, timeout=timeout)) as connection:
        with connection:
            yield connection


@dataclass(frozen=True)
class SMTPConfig:
    host: str
    port: int
    from_email: str
    username: str
    password: str
    use_ssl: bool
    use_starttls: bool


def smtp_config_from_environment():
    host = os.getenv("LIFELOG_SMTP_HOST", "").strip()
    from_email = os.getenv("LIFELOG_SMTP_FROM_EMAIL", "").strip()
    if not host or not from_email:
        raise ValueError(
            "Set LIFELOG_SMTP_HOST and LIFELOG_SMTP_FROM_EMAIL before starting "
            "the reminder worker."
        )

    try:
        port = int(os.getenv("LIFELOG_SMTP_PORT", "587"))
    except ValueError as error:
        raise ValueError("LIFELOG_SMTP_PORT must be a valid port number.") from error
    if not 1 <= port <= 65535:
        raise ValueError("LIFELOG_SMTP_PORT must be between 1 and 65535.")

    use_ssl = _environment_flag("LIFELOG_SMTP_USE_SSL", False)
    use_starttls = _environment_flag("LIFELOG_SMTP_USE_STARTTLS", True)
    if use_ssl and use_starttls:
        raise ValueError(
            "Enable only one of LIFELOG_SMTP_USE_SSL and "
            "LIFELOG_SMTP_USE_STARTTLS."
        )

    username = os.getenv("LIFELOG_SMTP_USERNAME", "").strip()
    password = os.getenv("LIFELOG_SMTP_PASSWORD", "")
    if bool(username) != bool(password):
        raise ValueError(
            "Set both LIFELOG_SMTP_USERNAME and LIFELOG_SMTP_PASSWORD, or leave "
            "both empty."
        )

    return SMTPConfig(
        host=host,
        port=port,
        from_email=from_email,
        username=username,
        password=password,
        use_ssl=use_ssl,
        use_starttls=use_starttls,
    )


def _environment_flag(name, default):
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized not in {"true", "false", "1", "0", "yes", "no"}:
        raise ValueError(f"{name} must be true or false.")
    return normalized in {"true", "1", "yes"}


def initialize_reminder_store(db_path):
    with _connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS reminder_deliveries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                due_date TEXT NOT NULL,
                scheduled_for TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                next_attempt_at TEXT NOT NULL,
                claimed_at TEXT,
                sent_at TEXT,
                last_error TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(task_id, due_date)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_reminder_deliveries_pending "
            "ON reminder_deliveries(status, next_attempt_at)"
        )


def _enqueue_due_reminders(connection, now):
    tasks = connection.execute(
        """
        SELECT tasks.id, tasks.due_date, profiles.reminder_time
        FROM tasks
        JOIN profiles ON profiles.user_id = tasks.user_id
        WHERE tasks.completed = 0
          AND tasks.reminder_enabled = 1
          AND tasks.due_date IS NOT NULL
          AND tasks.due_date <= ?
        """,
        (now.date().isoformat(),),
    ).fetchall()
    for task_id, due_date, reminder_time in tasks:
        try:
            scheduled = datetime.strptime(
                f"{due_date} {reminder_time}", "%Y-%m-%d %H:%M"
            )
        except (TypeError, ValueError):
            LOGGER.error(
                "Skipping reminder for task %s: invalid due date or profile time.",
                task_id,
            )
            continue
        if scheduled > now:
            continue
        scheduled_for = scheduled.isoformat(timespec="minutes")
        connection.execute(
            """
            INSERT OR IGNORE INTO reminder_deliveries
                (task_id, due_date, scheduled_for, next_attempt_at, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                task_id,
                due_date,
                scheduled_for,
                now.isoformat(timespec="seconds"),
                now.isoformat(timespec="seconds"),
            ),
        )


def _claim_due_reminders(db_path, now):
    now_text = now.isoformat(timespec="seconds")
    stale_before = (now - CLAIM_TIMEOUT).isoformat(timespec="seconds")
    with _connect(db_path, timeout=30) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("BEGIN IMMEDIATE")
        _enqueue_due_reminders(connection, now)
        connection.execute(
            """
            UPDATE reminder_deliveries
            SET status = 'pending', claimed_at = NULL
            WHERE status = 'processing' AND claimed_at < ?
            """,
            (stale_before,),
        )
        rows = connection.execute(
            """
            SELECT deliveries.id, deliveries.task_id, deliveries.due_date,
                   tasks.title, users.email
            FROM reminder_deliveries AS deliveries
            JOIN tasks ON tasks.id = deliveries.task_id
            JOIN users ON users.id = tasks.user_id
            WHERE deliveries.status = 'pending'
              AND deliveries.next_attempt_at <= ?
              AND tasks.completed = 0
              AND tasks.reminder_enabled = 1
              AND tasks.due_date = deliveries.due_date
            ORDER BY deliveries.scheduled_for, deliveries.id
            """,
            (now_text,),
        ).fetchall()
        connection.executemany(
            """
            UPDATE reminder_deliveries
            SET status = 'processing', claimed_at = ?
            WHERE id = ? AND status = 'pending'
            """,
            ((now_text, row["id"]) for row in rows),
        )
        connection.commit()
        return rows


def _send_email(config, recipient, task_title, due_date, smtp_factory=None):
    message = EmailMessage()
    message["Subject"] = f"LifeLog AI task reminder: {task_title}"
    message["From"] = config.from_email
    message["To"] = recipient
    message.set_content(
        f"This is a reminder for your LifeLog AI task:\n\n"
        f"{task_title}\nDue date: {due_date}\n\n"
        "You can review and update this task in your LifeLog AI workspace."
    )

    if smtp_factory is None:
        smtp_factory = smtplib.SMTP_SSL if config.use_ssl else smtplib.SMTP
    with smtp_factory(config.host, config.port, timeout=30) as server:
        if config.use_starttls:
            server.starttls()
        if config.username:
            server.login(config.username, config.password)
        refused = server.send_message(message)
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)


def _record_delivery_failure(db_path, delivery_id, error, now):
    with _connect(db_path, timeout=30) as connection:
        row = connection.execute(
            "SELECT attempts FROM reminder_deliveries WHERE id = ?",
            (delivery_id,),
        ).fetchone()
        if not row:
            raise LookupError(f"Reminder delivery {delivery_id} no longer exists.")
        attempts = row[0] + 1
        delay_minutes = min(5 * (2 ** min(attempts - 1, 16)), 360)
        next_attempt = (now + timedelta(minutes=delay_minutes)).isoformat(
            timespec="seconds"
        )
        connection.execute(
            """
            UPDATE reminder_deliveries
            SET status = 'pending', attempts = ?, next_attempt_at = ?,
                claimed_at = NULL, last_error = ?
            WHERE id = ?
            """,
            (attempts, next_attempt, _error_summary(error), delivery_id),
        )


def _error_summary(error):
    if isinstance(error, smtplib.SMTPRecipientsRefused):
        codes = sorted({str(details[0]) for details in error.recipients.values()})
        return "SMTP refused recipient (status " + ", ".join(codes) + ")"
    if isinstance(error, smtplib.SMTPResponseException):
        response = error.smtp_error
        if isinstance(response, bytes):
            response = response.decode("utf-8", errors="replace")
        return f"SMTP status {error.smtp_code}: {response}"
    return str(error).strip() or type(error).__name__


def run_reminder_cycle(db_path, smtp_config, now=None, smtp_factory=None):
    initialize_reminder_store(db_path)
    now = now or datetime.now()
    deliveries = _claim_due_reminders(db_path, now)
    sent = 0
    failed = 0
    for delivery in deliveries:
        try:
            _send_email(
                smtp_config,
                delivery["email"],
                delivery["title"],
                delivery["due_date"],
                smtp_factory,
            )
        except (OSError, smtplib.SMTPException, ValueError) as error:
            _record_delivery_failure(db_path, delivery["id"], error, now)
            LOGGER.error(
                "Reminder delivery %s failed: %s; it will be retried.",
                delivery["id"],
                _error_summary(error),
            )
            failed += 1
            continue

        with _connect(db_path, timeout=30) as connection:
            connection.execute(
                """
                UPDATE reminder_deliveries
                SET status = 'sent', sent_at = ?, claimed_at = NULL, last_error = NULL
                WHERE id = ?
                """,
                (now.isoformat(timespec="seconds"), delivery["id"]),
            )
        sent += 1
    return {"sent": sent, "failed": failed}


def run_worker(db_path, smtp_config, interval_seconds=60, once=False):
    if interval_seconds < 1:
        raise ValueError("The worker interval must be at least one second.")
    initialize_reminder_store(db_path)
    while True:
        result = run_reminder_cycle(db_path, smtp_config)
        if result["sent"] or result["failed"]:
            LOGGER.info(
                "Reminder cycle complete: %s sent, %s failed.",
                result["sent"],
                result["failed"],
            )
        if once:
            return
        time.sleep(interval_seconds)


def default_database_path():
    return Path(os.getenv("LIFELOG_DB_PATH", "lifelog.db"))
