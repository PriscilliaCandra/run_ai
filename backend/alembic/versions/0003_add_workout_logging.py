"""Add workout logging: training_plan_workouts, workout_logs, and
training_plans.start_date/status.

Purely additive, per PHASE_2_DESIGN.md Section 15:
- Two new tables. Nothing existing is touched by creating them.
- Two new NULLABLE columns on training_plans. Every existing row (anonymous
  research plans and Phase-1-era consumer plans) keeps start_date/status =
  NULL; no existing row is rewritten.

Research tables (runner_profiles, plan_evaluations) and research JSON
content are not touched by this migration at all.

Revision ID: 0003_workout_logging
Revises: 0002_add_auth
Create Date: 2026-09-29
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_workout_logging"
down_revision = "0002_add_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "training_plan_workouts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("training_plan_id", sa.String(36), sa.ForeignKey("training_plans.id", name="fk_tpw_training_plan_id"), nullable=False),
        sa.Column("week_number", sa.Integer, nullable=False),
        sa.Column("day_of_week", sa.String(10), nullable=False),
        sa.Column("workout_type", sa.String(30), nullable=False),
        sa.Column("distance_meters", sa.Integer, nullable=False),
        sa.Column("pace_target", sa.String(40), nullable=False),
        sa.Column("intensity_zone", sa.String(60), nullable=False),
        sa.Column("purpose", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.UniqueConstraint("training_plan_id", "week_number", "day_of_week", name="uq_tpw_plan_week_day"),
    )
    op.create_index("ix_tpw_plan_week", "training_plan_workouts", ["training_plan_id", "week_number"])
    op.create_index("ix_tpw_training_plan_id", "training_plan_workouts", ["training_plan_id"])

    op.create_table(
        "workout_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", name="fk_workout_logs_user_id"), nullable=False),
        sa.Column("workout_date", sa.Date, nullable=False),
        sa.Column("distance_meters", sa.Integer, nullable=False),
        sa.Column("duration_seconds", sa.Integer, nullable=False),
        sa.Column("workout_type", sa.String(20), nullable=False),
        sa.Column("avg_heart_rate", sa.Integer, nullable=True),
        sa.Column("max_heart_rate", sa.Integer, nullable=True),
        sa.Column("cadence_spm", sa.Integer, nullable=True),
        sa.Column("elevation_gain_m", sa.Integer, nullable=True),
        sa.Column("rpe", sa.Integer, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("training_plan_workout_id", sa.String(36), sa.ForeignKey("training_plan_workouts.id", name="fk_workout_logs_tpw_id"), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.Column("deleted_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_workout_logs_user_date", "workout_logs", ["user_id", "workout_date"])
    op.create_index("ix_workout_logs_user_deleted", "workout_logs", ["user_id", "deleted_at"])

    # Additive, nullable-first: every existing training_plans row (research
    # and Phase-1 consumer alike) keeps start_date/status = NULL.
    with op.batch_alter_table("training_plans") as batch_op:
        batch_op.add_column(sa.Column("start_date", sa.Date, nullable=True))
        batch_op.add_column(sa.Column("status", sa.String(20), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("training_plans") as batch_op:
        batch_op.drop_column("status")
        batch_op.drop_column("start_date")

    op.drop_index("ix_workout_logs_user_deleted", table_name="workout_logs")
    op.drop_index("ix_workout_logs_user_date", table_name="workout_logs")
    op.drop_table("workout_logs")

    op.drop_index("ix_tpw_training_plan_id", table_name="training_plan_workouts")
    op.drop_index("ix_tpw_plan_week", table_name="training_plan_workouts")
    op.drop_table("training_plan_workouts")
