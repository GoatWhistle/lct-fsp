"""Режим жюри: пометка тестовой учётки и лимит заданий экспресс-теста

Учётка — пометка `is_demo`: в выдаче и поиске реальных работодателей её нет. Попытка — лимит
заданий экспресс-теста; пусто у полного теста.

Revision ID: a7c3e91b5d28
Revises: a3d7c91e5b24
Create Date: 2026-10-10 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7c3e91b5d28"
down_revision: str | Sequence[str] | None = "a3d7c91e5b24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("is_demo", sa.Boolean(), server_default="false", nullable=False)
    )
    op.add_column("test_attempts", sa.Column("express_limit", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("test_attempts", "express_limit")
    op.drop_column("users", "is_demo")
