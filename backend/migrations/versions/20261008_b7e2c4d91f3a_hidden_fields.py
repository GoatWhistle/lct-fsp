"""Поля самоописания, скрытые кандидатом из обезличенной карточки

У профиля кандидата — множество скрытых полей. У существующих профилей оно пустое: по умолчанию
видно всё.

Revision ID: b7e2c4d91f3a
Revises: a8f8302329cf
Create Date: 2026-10-08 14:05:12.418201

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7e2c4d91f3a"
down_revision: str | Sequence[str] | None = "a8f8302329cf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "candidate_profiles",
        sa.Column(
            "hidden_fields",
            sa.ARRAY(sa.String(length=32)),
            server_default="{}",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        op.f("ck_candidate_profiles_hidden_fields"),
        "candidate_profiles",
        "hidden_fields <@ ARRAY['stack', 'experience_years', 'city', 'relocation', "
        "'industries']::varchar[]",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_candidate_profiles_hidden_fields"), "candidate_profiles", type_="check"
    )
    op.drop_column("candidate_profiles", "hidden_fields")
