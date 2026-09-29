"""Add auth tables (users, user_profiles, sessions, password_reset_tokens)
and a nullable user_id ownership column on training_plans.

This migration is purely ADDITIVE:
- Four new tables are created; nothing existing is touched.
- training_plans.user_id is added as NULLABLE, so every existing anonymous
  research row remains valid with user_id = NULL. No existing row is
  rewritten, and no existing table is dropped or recreated.
- plan_evaluations and runner_profiles are untouched entirely -- research
  data stays fully anonymous and unlinked to any user, by design.

Revision ID: 0002_add_auth
Revises: 0001_baseline
Create Date: 2026-09-29
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_add_auth"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("email_verified_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "user_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("age", sa.Integer, nullable=True),
        sa.Column("experience_level", sa.String(30), nullable=True),
        sa.Column("pb_5k", sa.String(10), nullable=True),
        sa.Column("pb_10k", sa.String(10), nullable=True),
        sa.Column("target_race_distance", sa.String(30), nullable=True),
        sa.Column("target_race_time", sa.String(10), nullable=True),
        sa.Column("current_weekly_mileage", sa.Float, nullable=True),
        sa.Column("training_days_per_week", sa.Integer, nullable=True),
        sa.Column("injury_limitations", sa.Text, nullable=True),
        sa.Column("easy_run_pace", sa.String(10), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_user_profiles_user_id", "user_profiles", ["user_id"], unique=True)

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("revoked_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_token_hash", "sessions", ["token_hash"], unique=True)

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("used_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    op.create_index("ix_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"], unique=True)

    # Additive, nullable-first: existing anonymous research plans keep user_id = NULL.
    # SQLite's batch mode rebuilds the table to add a FK, which requires the
    # constraint to be named explicitly.
    with op.batch_alter_table("training_plans") as batch_op:
        batch_op.add_column(
            sa.Column(
                "user_id",
                sa.String(36),
                sa.ForeignKey("users.id", name="fk_training_plans_user_id"),
                nullable=True,
            )
        )
    op.create_index("ix_training_plans_user_id", "training_plans", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_training_plans_user_id", table_name="training_plans")
    with op.batch_alter_table("training_plans") as batch_op:
        batch_op.drop_column("user_id")

    op.drop_index("ix_password_reset_tokens_token_hash", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")

    op.drop_index("ix_sessions_token_hash", table_name="sessions")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")

    op.drop_index("ix_user_profiles_user_id", table_name="user_profiles")
    op.drop_table("user_profiles")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
