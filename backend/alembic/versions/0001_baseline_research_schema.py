"""Baseline: existing research schema (runner_profiles, training_plans, plan_evaluations)

This migration documents the schema that already exists in
running_research.db, created historically via Base.metadata.create_all()
rather than Alembic. It is NOT meant to be run with `alembic upgrade` against
the existing database -- that database is baselined with:

    alembic stamp 0001_baseline

which records this revision as already-applied WITHOUT executing upgrade()
or touching any existing table or row. This migration's upgrade() only
matters for a brand-new, empty database (e.g. a fresh dev setup or CI),
where it recreates the same schema from scratch.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-09-29
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "runner_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("age", sa.Integer, nullable=False),
        sa.Column("gender", sa.String(20), nullable=False),
        sa.Column("experience_level", sa.String(30), nullable=False),
        sa.Column("pb_5k", sa.String(10), nullable=False),
        sa.Column("pb_10k", sa.String(10), nullable=True),
        sa.Column("target_race_distance", sa.String(30), nullable=False),
        sa.Column("target_race_time", sa.String(10), nullable=False),
        sa.Column("current_weekly_mileage", sa.Float, nullable=False),
        sa.Column("training_days_per_week", sa.Integer, nullable=False),
        sa.Column("preferred_training_days", sa.String(100), nullable=False),
        sa.Column("plan_duration_weeks", sa.Integer, nullable=False),
        sa.Column("injury_limitations", sa.Text, nullable=True),
        sa.Column("easy_run_pace", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=True),
    )

    op.create_table(
        "training_plans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("runner_profile_id", sa.String(36), sa.ForeignKey("runner_profiles.id"), nullable=False),
        sa.Column("calculated_vdot", sa.Float, nullable=False),
        sa.Column("target_pace", sa.String(10), nullable=False),
        sa.Column("rule_based_plan_json", sa.Text, nullable=False),
        sa.Column("ai_plan_json", sa.Text, nullable=False),
        sa.Column("explainability_summary", sa.Text, nullable=False),
        sa.Column("ai_model_used", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=True),
    )

    op.create_table(
        "plan_evaluations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("training_plan_id", sa.String(36), sa.ForeignKey("training_plans.id"), nullable=False),
        sa.Column("evaluated_plan_type", sa.String(20), nullable=False, server_default="ai_personalized"),
        sa.Column("personalization_score", sa.Integer, nullable=False),
        sa.Column("usefulness_score", sa.Integer, nullable=False),
        sa.Column("clarity_score", sa.Integer, nullable=False),
        sa.Column("confidence_score", sa.Integer, nullable=False),
        sa.Column("comments", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("plan_evaluations")
    op.drop_table("training_plans")
    op.drop_table("runner_profiles")
