"""Профиль кандидата: форма самоописания и ожидания

Revision ID: 09efe402b81c
Revises: a51e6a4909f8
Create Date: 2026-10-06 08:45:10.031151

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "09efe402b81c"
down_revision: str | Sequence[str] | None = "a51e6a4909f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "candidate_profiles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("contact_email", sa.String(length=320), nullable=False),
        sa.Column("contact_phone", sa.String(length=32), nullable=True),
        sa.Column("telegram", sa.String(length=32), nullable=True),
        sa.Column("about", sa.String(length=3000), nullable=False),
        sa.Column("job_roles", sa.ARRAY(sa.String(length=100)), nullable=False),
        sa.Column("experience_years", sa.Integer(), nullable=False),
        sa.Column("soft_skills", sa.ARRAY(sa.String(length=50)), nullable=False),
        sa.Column("work_formats", sa.ARRAY(sa.String(length=16)), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("relocation", sa.Boolean(), nullable=False),
        sa.Column("salary_from", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "cardinality(work_formats) > 0 "
            "AND work_formats <@ ARRAY['office', 'hybrid', 'remote']::varchar[]",
            name=op.f("ck_candidate_profiles_work_formats"),
        ),
        sa.CheckConstraint(
            "experience_years >= 0",
            name=op.f("ck_candidate_profiles_experience_years_not_negative"),
        ),
        sa.CheckConstraint(
            "salary_from > 0", name=op.f("ck_candidate_profiles_salary_from_positive")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_candidate_profiles_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_candidate_profiles")),
    )
    op.create_table(
        "candidate_technologies",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("technology_code", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["technology_code"],
            ["technologies.code"],
            name=op.f("fk_candidate_technologies_technology_code_technologies"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["candidate_profiles.user_id"],
            name=op.f("fk_candidate_technologies_user_id_candidate_profiles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "user_id", "technology_code", name=op.f("pk_candidate_technologies")
        ),
    )


def downgrade() -> None:
    op.drop_table("candidate_technologies")
    op.drop_table("candidate_profiles")
