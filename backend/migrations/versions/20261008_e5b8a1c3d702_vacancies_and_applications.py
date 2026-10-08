"""Вакансии работодателей и отклики кандидатов: вилка, записанный статус, отзыв доступа

Revision ID: e5b8a1c3d702
Revises: c4a9e2f71b05
Create Date: 2026-10-08 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5b8a1c3d702"
down_revision: str | Sequence[str] | None = "c4a9e2f71b05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vacancies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("employer_id", sa.Uuid(), nullable=False),
        sa.Column("company_name", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=5000), nullable=False),
        sa.Column("specialization_code", sa.String(length=32), nullable=False),
        sa.Column("grade_code", sa.String(length=32), nullable=False),
        sa.Column("work_formats", sa.ARRAY(sa.String(length=16)), nullable=False),
        sa.Column("salary_from", sa.Integer(), nullable=False),
        sa.Column("salary_to", sa.Integer(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "salary_from > 0 AND salary_from <= salary_to",
            name=op.f("ck_vacancies_salary_range"),
        ),
        sa.CheckConstraint(
            "cardinality(work_formats) > 0 "
            "AND work_formats <@ ARRAY['office', 'hybrid', 'remote']::varchar[]",
            name=op.f("ck_vacancies_work_formats"),
        ),
        sa.ForeignKeyConstraint(
            ["employer_id"],
            ["users.id"],
            name=op.f("fk_vacancies_employer_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["grade_code"], ["grades.code"], name=op.f("fk_vacancies_grade_code_grades")
        ),
        sa.ForeignKeyConstraint(
            ["specialization_code"],
            ["specializations.code"],
            name=op.f("fk_vacancies_specialization_code_specializations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vacancies")),
    )
    op.create_index(op.f("ix_vacancies_employer_id"), "vacancies", ["employer_id"], unique=False)
    op.create_index(
        "ix_vacancies_archived_at_published_at",
        "vacancies",
        ["archived_at", "published_at"],
        unique=False,
    )
    op.create_table(
        "applications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vacancy_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "sent",
                "viewed",
                "accepted",
                "declined",
                "expired",
                name="application_status",
                native_enum=False,
                create_constraint=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('sent', 'viewed', 'accepted', 'declined', 'expired')",
            name=op.f("ck_applications_application_status"),
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["users.id"],
            name=op.f("fk_applications_candidate_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["vacancy_id"],
            ["vacancies.id"],
            name=op.f("fk_applications_vacancy_id_vacancies"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_applications")),
        sa.UniqueConstraint("vacancy_id", "candidate_id", name=op.f("uq_applications_vacancy_id")),
    )
    op.create_index(
        op.f("ix_applications_candidate_id"), "applications", ["candidate_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_applications_candidate_id"), table_name="applications")
    op.drop_table("applications")
    op.drop_index("ix_vacancies_archived_at_published_at", table_name="vacancies")
    op.drop_index(op.f("ix_vacancies_employer_id"), table_name="vacancies")
    op.drop_table("vacancies")
