"""Карточка опыта в профиле кандидата

Записи опыта со слов кандидата — в раскрытой части профиля. У существующих профилей карточка
пустая.

Revision ID: e3b8d5a1c7f2
Revises: e5b8a1c3d702
Create Date: 2026-10-08 20:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e3b8d5a1c7f2"
down_revision: str | Sequence[str] | None = "e5b8a1c3d702"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "candidate_profiles",
        sa.Column(
            "experience",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("candidate_profiles", "experience")
