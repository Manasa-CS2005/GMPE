"""Add account-scoped memories, tasks, and mood check-ins.

Revision ID: 0002_account_memories_tasks
Revises: 0001_account_management
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_account_memories_tasks"
down_revision = "0001_account_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_memories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("mode", sa.String(length=40), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("tags", sa.Text(), nullable=False),
        sa.Column("mood", sa.String(length=24), nullable=False),
        sa.Column("memory_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["account_users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_account_memories_user_id", "account_memories", ["user_id"])

    op.create_table(
        "account_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("memory_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("due_time", sa.Time(), nullable=True),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.Column("reminder_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["account_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["memory_id"], ["account_memories.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_account_tasks_user_id", "account_tasks", ["user_id"])

    op.create_table(
        "account_moods",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("mood", sa.String(length=24), nullable=False),
        sa.Column("checkin_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["account_users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "checkin_date", name="uq_account_mood_user_date"),
    )
    op.create_index("ix_account_moods_user_id", "account_moods", ["user_id"])

    op.create_table(
        "account_reminders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=False),
        sa.Column("claimed_at", sa.DateTime(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["account_tasks.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("task_id", "scheduled_for", name="uq_account_reminder_task_time"),
    )
    op.create_index("ix_account_reminders_task_id", "account_reminders", ["task_id"])
    op.create_index(
        "ix_account_reminders_due",
        "account_reminders",
        ["status", "next_attempt_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_account_reminders_due", table_name="account_reminders")
    op.drop_index("ix_account_reminders_task_id", table_name="account_reminders")
    op.drop_table("account_reminders")
    op.drop_index("ix_account_moods_user_id", table_name="account_moods")
    op.drop_table("account_moods")
    op.drop_index("ix_account_tasks_user_id", table_name="account_tasks")
    op.drop_table("account_tasks")
    op.drop_index("ix_account_memories_user_id", table_name="account_memories")
    op.drop_table("account_memories")
