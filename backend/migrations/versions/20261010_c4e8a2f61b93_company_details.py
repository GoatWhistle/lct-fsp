"""Профиль компании: размер, аккредитация, бенефиты, ссылки, партнёрство с ФСП и логотип

Партнёрство отмечает федерация — через API профиля флаг не меняется. Логотип — картинка в
таблице, до 512 КБ.

Revision ID: c4e8a2f61b93
Revises: d8f3b2c5a716
Create Date: 2026-10-10 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c4e8a2f61b93"
down_revision: str | Sequence[str] | None = "d8f3b2c5a716"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("size", sa.String(16), nullable=True))
    op.add_column(
        "companies",
        sa.Column("it_accredited", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "companies",
        sa.Column("benefits", postgresql.ARRAY(sa.String(32)), server_default="{}", nullable=False),
    )
    op.add_column(
        "companies",
        sa.Column("links", postgresql.ARRAY(sa.String(300)), server_default="{}", nullable=False),
    )
    op.add_column(
        "companies",
        sa.Column("fsp_partner", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column("companies", sa.Column("logo", sa.LargeBinary(), nullable=True))
    op.add_column("companies", sa.Column("logo_type", sa.String(32), nullable=True))
    op.add_column(
        "companies", sa.Column("logo_updated_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    for column in (
        "logo_updated_at",
        "logo_type",
        "logo",
        "fsp_partner",
        "links",
        "benefits",
        "it_accredited",
        "size",
    ):
        op.drop_column("companies", column)
