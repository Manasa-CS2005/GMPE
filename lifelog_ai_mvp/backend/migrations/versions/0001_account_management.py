"""Create account, profile, session, token, and rate-limit tables.

Revision ID: 0001_account_management
Revises:
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_account_management"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("email_verified", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_account_users_email", "account_users", ["email"], unique=True)

    op.create_table(
        "account_profiles",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("avatar_data", sa.LargeBinary(), nullable=True),
        sa.Column("preferred_language", sa.String(length=16), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("writing_style", sa.String(length=32), nullable=False),
        sa.Column("journal_tone", sa.String(length=32), nullable=False),
        sa.Column("interests", sa.Text(), nullable=False),
        sa.Column("goals", sa.Text(), nullable=False),
        sa.Column("reminder_time", sa.String(length=5), nullable=False),
        sa.Column("email_notifications", sa.Boolean(), nullable=False),
        sa.Column("in_app_notifications", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["account_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "account_sessions",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["account_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    op.create_index("ix_account_sessions_user_id", "account_sessions", ["user_id"])
    op.create_index("ix_account_sessions_expires_at", "account_sessions", ["expires_at"])

    op.create_table(
        "account_tokens",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(length=24), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["account_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    op.create_index("ix_account_tokens_user_id", "account_tokens", ["user_id"])
    op.create_index("ix_account_tokens_expires_at", "account_tokens", ["expires_at"])

    op.create_table(
        "auth_rate_limits",
        sa.Column("action", sa.String(length=24), nullable=False),
        sa.Column("bucket_hash", sa.String(length=64), nullable=False),
        sa.Column("window_started_at", sa.DateTime(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("action", "bucket_hash"),
    )


def downgrade() -> None:
    op.drop_table("auth_rate_limits")
    op.drop_index("ix_account_tokens_expires_at", table_name="account_tokens")
    op.drop_index("ix_account_tokens_user_id", table_name="account_tokens")
    op.drop_table("account_tokens")
    op.drop_index("ix_account_sessions_expires_at", table_name="account_sessions")
    op.drop_index("ix_account_sessions_user_id", table_name="account_sessions")
    op.drop_table("account_sessions")
    op.drop_table("account_profiles")
    op.drop_index("ix_account_users_email", table_name="account_users")
    op.drop_table("account_users")
