"""Учётки, подтверждение email и справочники

Revision ID: 97899071653f
Revises:
Create Date: 2026-10-05 22:59:22.315125

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "97899071653f"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "grades",
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_grades")),
        sa.UniqueConstraint("rank", name=op.f("uq_grades_rank")),
    )
    op.create_table(
        "specializations",
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_specializations")),
    )
    op.create_table(
        "technologies",
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_technologies")),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "candidate",
                "employer",
                name="role",
                native_enum=False,
                create_constraint=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('candidate', 'employer')", name=op.f("ck_users_role")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "email_verification_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_email_verification_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_verification_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_email_verification_tokens_token_hash")),
    )
    op.create_index(
        op.f("ix_email_verification_tokens_user_id"),
        "email_verification_tokens",
        ["user_id"],
        unique=False,
    )
    op.create_table(
        "topics",
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("specialization_code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["specialization_code"],
            ["specializations.code"],
            name=op.f("fk_topics_specialization_code_specializations"),
        ),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_topics")),
    )
    op.create_index(
        op.f("ix_topics_specialization_code"), "topics", ["specialization_code"], unique=False
    )
    op.create_table(
        "technology_topics",
        sa.Column("technology_code", sa.String(length=64), nullable=False),
        sa.Column("topic_code", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["technology_code"],
            ["technologies.code"],
            name=op.f("fk_technology_topics_technology_code_technologies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["topic_code"],
            ["topics.code"],
            name=op.f("fk_technology_topics_topic_code_topics"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("technology_code", "topic_code", name=op.f("pk_technology_topics")),
    )


def downgrade() -> None:
    op.drop_table("technology_topics")
    op.drop_index(op.f("ix_topics_specialization_code"), table_name="topics")
    op.drop_table("topics")
    op.drop_index(
        op.f("ix_email_verification_tokens_user_id"), table_name="email_verification_tokens"
    )
    op.drop_table("email_verification_tokens")
    op.drop_table("users")
    op.drop_table("technologies")
    op.drop_table("specializations")
    op.drop_table("grades")
