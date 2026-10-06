"""Опрос без сферы бизнеса, интересные сферы — в профиле кандидата

«Отрасль» из ТЗ — IT-направление, то есть специализация: в опросе её уже выбирают. Сфера
бизнеса уходит из обязательного опроса в необязательное предпочтение профиля. Старые значения
не переносятся: поле было обязательным, первая сфера списка стояла выбранной по умолчанию, и
осознанный выбор от неё не отличить.

Revision ID: 7c604420b704
Revises: 8adaf94cba66
Create Date: 2026-10-07 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7c604420b704"
down_revision: str | Sequence[str] | None = "8adaf94cba66"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "candidate_industries",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("industry_code", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["industry_code"],
            ["industries.code"],
            name=op.f("fk_candidate_industries_industry_code_industries"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["candidate_profiles.user_id"],
            name=op.f("fk_candidate_industries_user_id_candidate_profiles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "industry_code", name=op.f("pk_candidate_industries")),
    )
    op.drop_constraint(op.f("fk_surveys_industry_code_industries"), "surveys", type_="foreignkey")
    op.drop_column("surveys", "industry_code")


def downgrade() -> None:
    # Обязательное поле возвращается первой сферой справочника — так опрос и заполнялся по
    # умолчанию.
    op.add_column("surveys", sa.Column("industry_code", sa.String(length=32), nullable=True))
    op.execute(
        "UPDATE surveys SET industry_code = (SELECT code FROM industries ORDER BY position LIMIT 1)"
    )
    op.alter_column("surveys", "industry_code", nullable=False)
    op.create_foreign_key(
        op.f("fk_surveys_industry_code_industries"),
        "surveys",
        "industries",
        ["industry_code"],
        ["code"],
    )
    op.drop_table("candidate_industries")
