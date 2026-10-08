"""Фильтры и шортлист подборки

У подборки — последние применённые фильтры и шортлист из кандидатов её выдачи. У существующих
подборок фильтров нет и шортлист пуст: открываются с исходной выдачей.

Revision ID: c4a7e91d2b60
Revises: b7e2c4d91f3a
Create Date: 2026-10-08 18:20:41.512094

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c4a7e91d2b60"
down_revision: str | Sequence[str] | None = "b7e2c4d91f3a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "selections",
        sa.Column(
            "filters",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
    )
    op.create_table(
        "selection_shortlist",
        sa.Column("selection_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["selection_id", "candidate_id"],
            ["selection_entries.selection_id", "selection_entries.candidate_id"],
            name=op.f("fk_selection_shortlist_selection_id_selection_entries"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "selection_id", "candidate_id", name=op.f("pk_selection_shortlist")
        ),
    )


def downgrade() -> None:
    op.drop_table("selection_shortlist")
    op.drop_column("selections", "filters")
