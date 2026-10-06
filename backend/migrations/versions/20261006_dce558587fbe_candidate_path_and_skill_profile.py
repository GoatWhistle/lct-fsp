"""Путь кандидата к категории и профиль навыков

Revision ID: dce558587fbe
Revises: 97899071653f
Create Date: 2026-10-06 07:37:28.032168

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "dce558587fbe"
down_revision: str | Sequence[str] | None = "97899071653f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "industries",
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_industries")),
    )
    op.create_table(
        "skill_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("specialization_code", sa.String(length=32), nullable=False),
        sa.Column("overall_theta", sa.Double(), nullable=False),
        sa.Column("overall_theta_sd", sa.Double(), nullable=False),
        sa.Column("observations", sa.Integer(), nullable=False),
        sa.Column("last_signal_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["specialization_code"],
            ["specializations.code"],
            name=op.f("fk_skill_profiles_specialization_code_specializations"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_skill_profiles_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_skill_profiles")),
        sa.UniqueConstraint(
            "user_id", "specialization_code", name=op.f("uq_skill_profiles_user_id")
        ),
    )
    op.create_table(
        "surveys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("industry_code", sa.String(length=32), nullable=False),
        sa.Column("specialization_code", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["industry_code"], ["industries.code"], name=op.f("fk_surveys_industry_code_industries")
        ),
        sa.ForeignKeyConstraint(
            ["specialization_code"],
            ["specializations.code"],
            name=op.f("fk_surveys_specialization_code_specializations"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_surveys_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_surveys")),
        sa.UniqueConstraint("user_id", "number", name=op.f("uq_surveys_user_id")),
    )
    op.create_table(
        "skill_profile_topics",
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("topic_code", sa.String(length=64), nullable=False),
        sa.Column("theta", sa.Double(), nullable=False),
        sa.Column("theta_sd", sa.Double(), nullable=False),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["skill_profiles.id"],
            name=op.f("fk_skill_profile_topics_profile_id_skill_profiles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["topic_code"], ["topics.code"], name=op.f("fk_skill_profile_topics_topic_code_topics")
        ),
        sa.PrimaryKeyConstraint("profile_id", "topic_code", name=op.f("pk_skill_profile_topics")),
    )
    op.create_table(
        "test_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("survey_id", sa.Uuid(), nullable=False),
        sa.Column("specialization_code", sa.String(length=32), nullable=False),
        sa.Column("grade_code", sa.String(length=32), nullable=False),
        sa.Column("continues_attempt_id", sa.Uuid(), nullable=True),
        sa.Column("blueprint", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("overall_theta", sa.Double(), nullable=True),
        sa.Column("overall_theta_sd", sa.Double(), nullable=True),
        sa.Column(
            "outcome",
            sa.Enum(
                "assigned",
                "offered",
                "no_category",
                name="attempt_outcome",
                native_enum=False,
                create_constraint=False,
                length=16,
            ),
            nullable=True,
        ),
        sa.Column("outcome_grade_code", sa.String(length=32), nullable=True),
        sa.Column("retest_after", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "outcome IN ('assigned', 'offered', 'no_category')",
            name=op.f("ck_test_attempts_attempt_outcome"),
        ),
        sa.ForeignKeyConstraint(
            ["continues_attempt_id"],
            ["test_attempts.id"],
            name=op.f("fk_test_attempts_continues_attempt_id_test_attempts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["grade_code"], ["grades.code"], name=op.f("fk_test_attempts_grade_code_grades")
        ),
        sa.ForeignKeyConstraint(
            ["outcome_grade_code"],
            ["grades.code"],
            name=op.f("fk_test_attempts_outcome_grade_code_grades"),
        ),
        sa.ForeignKeyConstraint(
            ["specialization_code"],
            ["specializations.code"],
            name=op.f("fk_test_attempts_specialization_code_specializations"),
        ),
        sa.ForeignKeyConstraint(
            ["survey_id"],
            ["surveys.id"],
            name=op.f("fk_test_attempts_survey_id_surveys"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_test_attempts_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_test_attempts")),
        sa.UniqueConstraint(
            "continues_attempt_id", name=op.f("uq_test_attempts_continues_attempt_id")
        ),
        sa.UniqueConstraint("user_id", "number", name=op.f("uq_test_attempts_user_id")),
    )
    op.create_table(
        "candidate_categories",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("specialization_code", sa.String(length=32), nullable=False),
        sa.Column("grade_code", sa.String(length=32), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["test_attempts.id"],
            name=op.f("fk_candidate_categories_attempt_id_test_attempts"),
        ),
        sa.ForeignKeyConstraint(
            ["grade_code"], ["grades.code"], name=op.f("fk_candidate_categories_grade_code_grades")
        ),
        sa.ForeignKeyConstraint(
            ["specialization_code"],
            ["specializations.code"],
            name=op.f("fk_candidate_categories_specialization_code_specializations"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_candidate_categories_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_candidate_categories")),
    )
    op.create_table(
        "presentations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("family_code", sa.String(length=128), nullable=False),
        sa.Column("topic_code", sa.String(length=64), nullable=False),
        sa.Column("seed", sa.BigInteger(), nullable=False),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("discrimination", sa.Double(), nullable=False),
        sa.Column("difficulty", sa.Double(), nullable=False),
        sa.Column("topic_theta_before", sa.Double(), nullable=False),
        sa.Column("topic_theta_sd_before", sa.Double(), nullable=False),
        sa.Column("shown_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("response", sa.String(length=500), nullable=True),
        sa.Column("correct", sa.Boolean(), nullable=True),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["test_attempts.id"],
            name=op.f("fk_presentations_attempt_id_test_attempts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["topic_code"], ["topics.code"], name=op.f("fk_presentations_topic_code_topics")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_presentations")),
        sa.UniqueConstraint("attempt_id", "position", name=op.f("uq_presentations_attempt_id")),
    )
    op.create_index(
        op.f("ix_presentations_family_code"), "presentations", ["family_code"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_presentations_family_code"), table_name="presentations")
    op.drop_table("presentations")
    op.drop_table("candidate_categories")
    op.drop_table("test_attempts")
    op.drop_table("skill_profile_topics")
    op.drop_table("surveys")
    op.drop_table("skill_profiles")
    op.drop_table("industries")
