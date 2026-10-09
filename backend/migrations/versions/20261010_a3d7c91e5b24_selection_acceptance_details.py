"""Признаки и SHAP-объяснение P(принятия) в строках подборки

Подсказка по вилке считается по признакам строки на момент построения подборки, объяснение
показывается в выдаче. У старых подборок и у подборок без модели принятия поле пустое.

Revision ID: a3d7c91e5b24
Revises: e5b2d8c41f07
Create Date: 2026-10-10 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a3d7c91e5b24"
down_revision: str | Sequence[str] | None = "e5b2d8c41f07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "selection_entries",
        sa.Column("acceptance", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("selection_entries", "acceptance")
