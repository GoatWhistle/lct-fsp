"""Подборка: снимок потребности и выдача со скорами и вкладами

Revision ID: 68df9fb9894f
Revises: 09efe402b81c
Create Date: 2026-10-06 12:27:15.944499

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "68df9fb9894f"
down_revision: str | Sequence[str] | None = "09efe402b81c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "selections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("need_id", sa.Uuid(), nullable=True),
        sa.Column("need_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("stack_cap", sa.Double(), nullable=False),
        sa.Column("exact_total", sa.Integer(), nullable=False),
        sa.Column("nearby_total", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["need_id"], ["needs.id"], name=op.f("fk_selections_need_id_needs"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_selections_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_selections")),
    )
    op.create_index(op.f("ix_selections_need_id"), "selections", ["need_id"], unique=False)
    op.create_index(op.f("ix_selections_user_id"), "selections", ["user_id"], unique=False)
    op.create_table(
        "selection_entries",
        sa.Column("selection_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column(
            "block",
            sa.Enum(
                "exact",
                "nearby",
                name="selection_block",
                native_enum=False,
                create_constraint=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("grade_code", sa.String(length=32), nullable=False),
        sa.Column("match_score", sa.Double(), nullable=False),
        sa.Column("acceptance_probability", sa.Double(), nullable=True),
        sa.Column("mutual_score", sa.Double(), nullable=False),
        sa.Column("explanation", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("stale", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "block IN ('exact', 'nearby')", name=op.f("ck_selection_entries_selection_block")
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["users.id"],
            name=op.f("fk_selection_entries_candidate_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["grade_code"], ["grades.code"], name=op.f("fk_selection_entries_grade_code_grades")
        ),
        sa.ForeignKeyConstraint(
            ["selection_id"],
            ["selections.id"],
            name=op.f("fk_selection_entries_selection_id_selections"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("selection_id", "position", name=op.f("pk_selection_entries")),
        sa.UniqueConstraint(
            "selection_id", "candidate_id", name=op.f("uq_selection_entries_selection_id")
        ),
    )
    op.create_index(
        op.f("ix_selection_entries_candidate_id"),
        "selection_entries",
        ["candidate_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_selection_entries_candidate_id"), table_name="selection_entries")
    op.drop_table("selection_entries")
    op.drop_index(op.f("ix_selections_user_id"), table_name="selections")
    op.drop_index(op.f("ix_selections_need_id"), table_name="selections")
    op.drop_table("selections")
