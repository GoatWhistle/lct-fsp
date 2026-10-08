"""Блок по теме: назначение попытки `topic_block` и тема блока

Блок — короткая попытка по одной теме категории: уточняет профиль навыков, категорию и грейд не
меняет. Тема хранится у попытки — по ней считается интервал блока.

Revision ID: c4a9e2f71b05
Revises: c4a7e91d2b60
Create Date: 2026-10-08 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4a9e2f71b05"
down_revision: str | Sequence[str] | None = "c4a7e91d2b60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("test_attempts", sa.Column("topic_code", sa.String(length=64), nullable=True))
    op.create_foreign_key(
        op.f("fk_test_attempts_topic_code_topics"),
        "test_attempts",
        "topics",
        ["topic_code"],
        ["code"],
    )
    op.drop_constraint(op.f("ck_test_attempts_attempt_purpose"), "test_attempts", type_="check")
    op.create_check_constraint(
        op.f("ck_test_attempts_attempt_purpose"),
        "test_attempts",
        "purpose IN ('determination', 'grade_up', 'topic_block')",
    )
    op.create_check_constraint(
        op.f("ck_test_attempts_topic_block_topic"),
        "test_attempts",
        "(purpose = 'topic_block') = (topic_code IS NOT NULL)",
    )


def downgrade() -> None:
    # Блоки прежняя схема не выразит — они удаляются вместе с предъявлениями.
    op.drop_constraint(op.f("ck_test_attempts_topic_block_topic"), "test_attempts", type_="check")
    op.execute("DELETE FROM test_attempts WHERE purpose = 'topic_block'")
    op.drop_constraint(op.f("ck_test_attempts_attempt_purpose"), "test_attempts", type_="check")
    op.create_check_constraint(
        op.f("ck_test_attempts_attempt_purpose"),
        "test_attempts",
        "purpose IN ('determination', 'grade_up')",
    )
    op.drop_constraint(
        op.f("fk_test_attempts_topic_code_topics"), "test_attempts", type_="foreignkey"
    )
    op.drop_column("test_attempts", "topic_code")
