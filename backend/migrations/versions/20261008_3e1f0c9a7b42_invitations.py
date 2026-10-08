"""Приглашения работодателей кандидатам: вилка, способ связи, записанный статус

Revision ID: 3e1f0c9a7b42
Revises: 7c604420b704
Create Date: 2026-10-08 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3e1f0c9a7b42"
down_revision: str | Sequence[str] | None = "7c604420b704"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invitations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("employer_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("company_name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=3000), nullable=False),
        sa.Column("salary_from", sa.Integer(), nullable=False),
        sa.Column("salary_to", sa.Integer(), nullable=False),
        sa.Column("contact", sa.String(length=300), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "sent",
                "viewed",
                "accepted",
                "declined",
                "expired",
                name="invitation_status",
                native_enum=False,
                create_constraint=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "salary_from > 0 AND salary_from <= salary_to",
            name=op.f("ck_invitations_salary_range"),
        ),
        sa.CheckConstraint(
            "status IN ('sent', 'viewed', 'accepted', 'declined', 'expired')",
            name=op.f("ck_invitations_invitation_status"),
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["users.id"],
            name=op.f("fk_invitations_candidate_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["employer_id"],
            ["users.id"],
            name=op.f("fk_invitations_employer_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invitations")),
    )
    op.create_index(
        op.f("ix_invitations_candidate_id"), "invitations", ["candidate_id"], unique=False
    )
    op.create_index(
        "ix_invitations_employer_id_candidate_id",
        "invitations",
        ["employer_id", "candidate_id"],
        unique=False,
    )
    op.create_index(
        "ix_invitations_employer_id_sent_at",
        "invitations",
        ["employer_id", "sent_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_invitations_employer_id_sent_at", table_name="invitations")
    op.drop_index("ix_invitations_employer_id_candidate_id", table_name="invitations")
    op.drop_index(op.f("ix_invitations_candidate_id"), table_name="invitations")
    op.drop_table("invitations")
