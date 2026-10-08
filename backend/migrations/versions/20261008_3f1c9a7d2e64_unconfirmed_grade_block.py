"""Нижний блок подборки — неподтверждённый грейд, статус грейда в записи выдачи

Записи нижнего блока без скора по темам: соответствие и взаимный скор — NULL. Статус и
заявленный грейд старых записей восстанавливаются по текущей категории кандидата, если она та же,
что в записи: специализация потребности подборки и грейд совпадают, присвоена до построения.
Иначе запись считается подтверждённой — заявка той категории не известна.

Revision ID: 3f1c9a7d2e64
Revises: 5abf1dffb9d7
Create Date: 2026-10-08 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3f1c9a7d2e64"
down_revision: str | Sequence[str] | None = "5abf1dffb9d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "selection_entries"

BACKFILL_BELOW_CLAIMED = """
WITH RECURSIVE chain AS (
    SELECT c.user_id, a.grade_code, a.continues_attempt_id
    FROM candidate_categories c
    JOIN test_attempts a ON a.id = c.attempt_id
    UNION ALL
    SELECT chain.user_id, a.grade_code, a.continues_attempt_id
    FROM chain
    JOIN test_attempts a ON a.id = chain.continues_attempt_id
),
roots AS (
    SELECT chain.user_id, g.code, g.name, g.rank
    FROM chain
    JOIN grades g ON g.code = chain.grade_code
    WHERE chain.continues_attempt_id IS NULL
)
UPDATE selection_entries e
SET grade_status = 'below_claimed', claimed_grade_code = r.code, claimed_grade_name = r.name
FROM roots r, candidate_categories c, grades cg, selections s
WHERE r.user_id = e.candidate_id
    AND c.user_id = e.candidate_id
    AND s.id = e.selection_id
    AND c.specialization_code = s.need_snapshot -> 'specialization' ->> 'code'
    AND c.assigned_at <= s.created_at
    AND c.grade_code = e.grade_code
    AND cg.code = e.grade_code
    AND r.rank > cg.rank
"""


def upgrade() -> None:
    op.drop_constraint(op.f("ck_selection_entries_selection_block"), TABLE, type_="check")
    op.create_check_constraint(
        op.f("ck_selection_entries_selection_block"),
        TABLE,
        "block IN ('exact', 'nearby', 'unconfirmed')",
    )
    op.add_column(TABLE, sa.Column("grade_status", sa.String(length=16), nullable=True))
    op.add_column(TABLE, sa.Column("claimed_grade_code", sa.String(length=32), nullable=True))
    op.add_column(TABLE, sa.Column("claimed_grade_name", sa.String(length=64), nullable=True))
    op.execute(
        "UPDATE selection_entries SET grade_status = 'confirmed', "
        "claimed_grade_code = grade_code, claimed_grade_name = grade_name"
    )
    op.execute(BACKFILL_BELOW_CLAIMED)
    for column in ("grade_status", "claimed_grade_code", "claimed_grade_name"):
        op.alter_column(TABLE, column, nullable=False)
    op.create_check_constraint(
        op.f("ck_selection_entries_grade_status"),
        TABLE,
        "grade_status IN ('confirmed', 'below_claimed', 'unconfirmed')",
    )
    op.alter_column(TABLE, "match_score", nullable=True)
    op.alter_column(TABLE, "mutual_score", nullable=True)


def downgrade() -> None:
    # Нижнего блока до этой ревизии не было: его записи уходят из подборок.
    op.execute("DELETE FROM selection_entries WHERE block = 'unconfirmed'")
    op.alter_column(TABLE, "mutual_score", nullable=False)
    op.alter_column(TABLE, "match_score", nullable=False)
    op.drop_constraint(op.f("ck_selection_entries_grade_status"), TABLE, type_="check")
    op.drop_column(TABLE, "claimed_grade_name")
    op.drop_column(TABLE, "claimed_grade_code")
    op.drop_column(TABLE, "grade_status")
    op.drop_constraint(op.f("ck_selection_entries_selection_block"), TABLE, type_="check")
    op.create_check_constraint(
        op.f("ck_selection_entries_selection_block"), TABLE, "block IN ('exact', 'nearby')"
    )
