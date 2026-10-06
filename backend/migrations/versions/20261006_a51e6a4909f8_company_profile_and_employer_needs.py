"""Профиль компании и потребности работодателя

Revision ID: a51e6a4909f8
Revises: dce558587fbe
Create Date: 2026-10-06 08:05:55.256805

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a51e6a4909f8"
down_revision: str | Sequence[str] | None = "dce558587fbe"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("industry_code", sa.String(length=32), nullable=False),
        sa.Column("description", sa.String(length=3000), nullable=False),
        sa.Column("website", sa.String(length=300), nullable=True),
        sa.Column("contact_email", sa.String(length=320), nullable=False),
        sa.Column("contact_phone", sa.String(length=32), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["industry_code"],
            ["industries.code"],
            name=op.f("fk_companies_industry_code_industries"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_companies_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_companies")),
    )
    op.create_table(
        "needs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("team_description", sa.String(length=2000), nullable=False),
        sa.Column("specialization_code", sa.String(length=32), nullable=False),
        sa.Column("grade_code", sa.String(length=32), nullable=False),
        sa.Column(
            "work_format",
            sa.Enum(
                "office",
                "hybrid",
                "remote",
                name="work_format",
                native_enum=False,
                create_constraint=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("salary_from", sa.Integer(), nullable=True),
        sa.Column("salary_to", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "work_format IN ('office', 'hybrid', 'remote')", name=op.f("ck_needs_work_format")
        ),
        sa.CheckConstraint(
            "(salary_from IS NULL AND salary_to IS NULL) OR "
            "(salary_from IS NOT NULL AND salary_to IS NOT NULL "
            "AND salary_from > 0 AND salary_from <= salary_to)",
            name=op.f("ck_needs_salary_range"),
        ),
        sa.ForeignKeyConstraint(
            ["grade_code"], ["grades.code"], name=op.f("fk_needs_grade_code_grades")
        ),
        sa.ForeignKeyConstraint(
            ["specialization_code"],
            ["specializations.code"],
            name=op.f("fk_needs_specialization_code_specializations"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_needs_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_needs")),
    )
    op.create_index(op.f("ix_needs_user_id"), "needs", ["user_id"], unique=False)
    op.create_table(
        "need_technologies",
        sa.Column("need_id", sa.Uuid(), nullable=False),
        sa.Column("technology_code", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["need_id"],
            ["needs.id"],
            name=op.f("fk_need_technologies_need_id_needs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["technology_code"],
            ["technologies.code"],
            name=op.f("fk_need_technologies_technology_code_technologies"),
        ),
        sa.PrimaryKeyConstraint("need_id", "technology_code", name=op.f("pk_need_technologies")),
    )
    op.create_table(
        "need_topic_importances",
        sa.Column("need_id", sa.Uuid(), nullable=False),
        sa.Column("topic_code", sa.String(length=64), nullable=False),
        sa.Column(
            "importance",
            sa.Enum(
                "key",
                "important",
                "nice",
                name="topic_importance",
                native_enum=False,
                create_constraint=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.CheckConstraint(
            "importance IN ('key', 'important', 'nice')",
            name=op.f("ck_need_topic_importances_topic_importance"),
        ),
        sa.ForeignKeyConstraint(
            ["need_id"],
            ["needs.id"],
            name=op.f("fk_need_topic_importances_need_id_needs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["topic_code"],
            ["topics.code"],
            name=op.f("fk_need_topic_importances_topic_code_topics"),
        ),
        sa.PrimaryKeyConstraint("need_id", "topic_code", name=op.f("pk_need_topic_importances")),
    )


def downgrade() -> None:
    op.drop_table("need_topic_importances")
    op.drop_table("need_technologies")
    op.drop_index(op.f("ix_needs_user_id"), table_name="needs")
    op.drop_table("needs")
    op.drop_table("companies")
