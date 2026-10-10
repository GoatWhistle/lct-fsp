"""Согласие попытки с моделью: l_z определения на остановке

Пишется при остановке попытки пути — для стенда и разбора; наружу не отдаётся.

Revision ID: d8f3b2c5a716
Revises: c6d1a9e4f357
Create Date: 2026-10-10 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d8f3b2c5a716"
down_revision: str | Sequence[str] | None = "c6d1a9e4f357"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("test_attempts", sa.Column("person_fit", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("test_attempts", "person_fit")
