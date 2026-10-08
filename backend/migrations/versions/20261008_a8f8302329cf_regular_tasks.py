"""Регулярные задания работодателей и ответы кандидатов, источник уверенности в профиле

Задания и ответы — новые таблицы. У темы профиля навыков — признак, что в её уровень вошли
ответы на регулярные задания: подборка показывает его источником уверенности. В объяснениях уже
сохранённых подборок у тем появляется тот же признак — `false`: регулярных заданий тогда не было.

Revision ID: a8f8302329cf
Revises: 5d1e0b7a2c94
Create Date: 2026-10-08 10:21:55.022372

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a8f8302329cf"
down_revision: str | Sequence[str] | None = "5d1e0b7a2c94"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Объяснение подборки — формат кодеков `app.repository.selection`: признак у каждой темы.
EXPLANATION_UPGRADE = """
UPDATE selection_entries SET explanation = jsonb_set(
    explanation,
    '{topics}',
    (
        SELECT coalesce(jsonb_agg(t || '{"regular_task": false}'::jsonb ORDER BY i), '[]'::jsonb)
        FROM jsonb_array_elements(explanation -> 'topics') WITH ORDINALITY AS e(t, i)
    )
)
"""
EXPLANATION_DOWNGRADE = """
UPDATE selection_entries SET explanation = jsonb_set(
    explanation,
    '{topics}',
    (
        SELECT coalesce(jsonb_agg(t - 'regular_task' ORDER BY i), '[]'::jsonb)
        FROM jsonb_array_elements(explanation -> 'topics') WITH ORDINALITY AS e(t, i)
    )
)
"""


def upgrade() -> None:
    op.create_table(
        "regular_tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("specialization_code", sa.String(length=32), nullable=False),
        sa.Column("grade_code", sa.String(length=32), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "reference",
                "open",
                name="task_kind",
                native_enum=False,
                create_constraint=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("prompt", sa.String(length=4000), nullable=False),
        sa.Column("reference_answer", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(kind = 'reference') = (reference_answer IS NOT NULL)",
            name=op.f("ck_regular_tasks_reference_answer"),
        ),
        sa.CheckConstraint(
            "kind IN ('reference', 'open')", name=op.f("ck_regular_tasks_task_kind")
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
            name=op.f("fk_regular_tasks_author_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["grade_code"], ["grades.code"], name=op.f("fk_regular_tasks_grade_code_grades")
        ),
        sa.ForeignKeyConstraint(
            ["specialization_code"],
            ["specializations.code"],
            name=op.f("fk_regular_tasks_specialization_code_specializations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_regular_tasks")),
    )
    op.create_index(
        op.f("ix_regular_tasks_author_id"), "regular_tasks", ["author_id"], unique=False
    )
    op.create_index(
        op.f("ix_regular_tasks_specialization_code"),
        "regular_tasks",
        ["specialization_code"],
        unique=False,
    )
    op.create_table(
        "regular_task_answers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("response", sa.String(length=4000), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correct", sa.Boolean(), nullable=True),
        sa.Column("rubric", sa.SmallInteger(), nullable=True),
        sa.Column("graded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(rubric IS NULL) = (graded_at IS NULL)", name=op.f("ck_regular_task_answers_graded_at")
        ),
        sa.CheckConstraint(
            "correct IS NULL OR rubric IS NULL", name=op.f("ck_regular_task_answers_one_verdict")
        ),
        sa.CheckConstraint(
            "rubric BETWEEN 0 AND 3", name=op.f("ck_regular_task_answers_rubric_range")
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["users.id"],
            name=op.f("fk_regular_task_answers_candidate_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["regular_tasks.id"],
            name=op.f("fk_regular_task_answers_task_id_regular_tasks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_regular_task_answers")),
        sa.UniqueConstraint(
            "task_id", "candidate_id", name=op.f("uq_regular_task_answers_task_id")
        ),
    )
    op.create_index(
        op.f("ix_regular_task_answers_candidate_id"),
        "regular_task_answers",
        ["candidate_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_regular_task_answers_task_id"), "regular_task_answers", ["task_id"], unique=False
    )
    op.create_table(
        "regular_task_topics",
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("topic_code", sa.String(length=64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["regular_tasks.id"],
            name=op.f("fk_regular_task_topics_task_id_regular_tasks"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["topic_code"], ["topics.code"], name=op.f("fk_regular_task_topics_topic_code_topics")
        ),
        sa.PrimaryKeyConstraint("task_id", "topic_code", name=op.f("pk_regular_task_topics")),
    )
    op.add_column(
        "skill_profile_topics",
        sa.Column("regular_task", sa.Boolean(), server_default="false", nullable=False),
    )
    op.execute(EXPLANATION_UPGRADE)


def downgrade() -> None:
    op.execute(EXPLANATION_DOWNGRADE)
    op.drop_column("skill_profile_topics", "regular_task")
    op.drop_table("regular_task_topics")
    op.drop_index(op.f("ix_regular_task_answers_task_id"), table_name="regular_task_answers")
    op.drop_index(op.f("ix_regular_task_answers_candidate_id"), table_name="regular_task_answers")
    op.drop_table("regular_task_answers")
    op.drop_index(op.f("ix_regular_tasks_specialization_code"), table_name="regular_tasks")
    op.drop_index(op.f("ix_regular_tasks_author_id"), table_name="regular_tasks")
    op.drop_table("regular_tasks")
