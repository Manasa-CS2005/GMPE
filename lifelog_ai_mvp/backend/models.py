from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class AccountUser(Base):
    __tablename__ = "account_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AccountProfile(Base):
    __tablename__ = "account_profiles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("account_users.id", ondelete="CASCADE"), primary_key=True
    )
    avatar_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(16), default="en", nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    writing_style: Mapped[str] = mapped_column(String(32), default="Reflective", nullable=False)
    journal_tone: Mapped[str] = mapped_column(String(32), default="Warm", nullable=False)
    interests: Mapped[str] = mapped_column(Text, default="", nullable=False)
    goals: Mapped[str] = mapped_column(Text, default="", nullable=False)
    reminder_time: Mapped[str] = mapped_column(String(5), default="09:00", nullable=False)
    email_notifications: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    in_app_notifications: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AccountSession(Base):
    __tablename__ = "account_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("account_users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AccountToken(Base):
    __tablename__ = "account_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("account_users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    purpose: Mapped[str] = mapped_column(String(24), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AuthRateLimit(Base):
    __tablename__ = "auth_rate_limits"

    action: Mapped[str] = mapped_column(String(24), primary_key=True)
    bucket_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class AccountMemory(Base):
    __tablename__ = "account_memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("account_users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(String(40), default="Simple Journal", nullable=False)
    result_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    tags: Mapped[str] = mapped_column(Text, default="", nullable=False)
    mood: Mapped[str] = mapped_column(String(24), default="", nullable=False)
    memory_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AccountTask(Base):
    __tablename__ = "account_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("account_users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    memory_id: Mapped[int | None] = mapped_column(
        ForeignKey("account_memories.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    priority: Mapped[str] = mapped_column(String(16), default="normal", nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reminder_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AccountMood(Base):
    __tablename__ = "account_moods"
    __table_args__ = (
        UniqueConstraint("user_id", "checkin_date", name="uq_account_mood_user_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("account_users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    mood: Mapped[str] = mapped_column(String(24), nullable=False)
    checkin_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AccountReminder(Base):
    __tablename__ = "account_reminders"
    __table_args__ = (
        UniqueConstraint("task_id", "scheduled_for", name="uq_account_reminder_task_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("account_tasks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    scheduled_for: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
