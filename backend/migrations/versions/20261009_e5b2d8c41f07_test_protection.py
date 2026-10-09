"""Защита теста: детектор дрейфа, флаги времени, события с согласия и проверочный блок

Семейство помнит статистику CUSUM и момент, когда его пометили скомпрометированным. Предъявление —
счётчики событий, флаг времени и выпавший ответ. Попытка — согласие на события, отложенные
наблюдения, а проверочный блок — что он проверяет, срок и итог. Категория — пометку «уровень
подтверждён».

Revision ID: e5b2d8c41f07
Revises: e3b8d5a1c7f2
Create Date: 2026-10-09 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5b2d8c41f07"
down_revision: str | Sequence[str] | None = "e3b8d5a1c7f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PURPOSES = ("determination", "grade_up", "topic_block")
OUTCOMES = ("assigned", "offered", "no_category", "not_passed")
STATUSES = ("active", "review")


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _replace_check(table: str, name: str, condition: str) -> None:
    op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, condition)


def upgrade() -> None:
    op.add_column(
        "family_calibrations",
        sa.Column("drift_cusum", sa.Float(), server_default="0", nullable=False),
    )
    op.add_column(
        "family_calibrations",
        sa.Column("compromised_at", sa.DateTime(timezone=True), nullable=True),
    )
    _replace_check(
        "family_calibrations", "family_status", _in("status", (*STATUSES, "compromised"))
    )

    op.add_column("presentations", sa.Column("paste_events", sa.Integer(), nullable=True))
    op.add_column("presentations", sa.Column("focus_losses", sa.Integer(), nullable=True))
    op.add_column("presentations", sa.Column("time_flag", sa.Boolean(), nullable=True))
    op.add_column(
        "presentations",
        sa.Column("dropped", sa.Boolean(), server_default="false", nullable=False),
    )

    op.add_column(
        "test_attempts",
        sa.Column("focus_consent", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "test_attempts",
        sa.Column("withheld", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column("test_attempts", sa.Column("verifies_attempt_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_test_attempts_verifies_attempt_id_test_attempts"),
        "test_attempts",
        "test_attempts",
        ["verifies_attempt_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.add_column("test_attempts", sa.Column("deadline", sa.DateTime(timezone=True), nullable=True))
    op.add_column("test_attempts", sa.Column("expected_correct", sa.Float(), nullable=True))
    op.add_column("test_attempts", sa.Column("correct_count", sa.Integer(), nullable=True))
    op.add_column("test_attempts", sa.Column("planned_items", sa.Integer(), nullable=True))
    _replace_check("test_attempts", "attempt_purpose", _in("purpose", (*PURPOSES, "verification")))
    _replace_check(
        "test_attempts",
        "attempt_outcome",
        _in("outcome", (*OUTCOMES, "verification", "confirmed", "mismatch")),
    )
    op.create_check_constraint(
        op.f("ck_test_attempts_verification_deadline"),
        "test_attempts",
        "(purpose = 'verification') = (deadline IS NOT NULL)",
    )

    op.add_column(
        "candidate_categories",
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    # Проверочные блоки прежняя схема не выразит — они удаляются вместе с предъявлениями;
    # отложенные результаты остаются попытками без категории.
    op.drop_column("candidate_categories", "verified_at")

    op.drop_constraint(
        op.f("ck_test_attempts_verification_deadline"), "test_attempts", type_="check"
    )
    op.execute("DELETE FROM test_attempts WHERE purpose = 'verification'")
    op.execute("UPDATE test_attempts SET outcome = 'not_passed' WHERE outcome = 'verification'")
    _replace_check("test_attempts", "attempt_outcome", _in("outcome", OUTCOMES))
    _replace_check("test_attempts", "attempt_purpose", _in("purpose", PURPOSES))
    op.drop_column("test_attempts", "planned_items")
    op.drop_column("test_attempts", "correct_count")
    op.drop_column("test_attempts", "expected_correct")
    op.drop_column("test_attempts", "deadline")
    op.drop_constraint(
        op.f("fk_test_attempts_verifies_attempt_id_test_attempts"),
        "test_attempts",
        type_="foreignkey",
    )
    op.drop_column("test_attempts", "verifies_attempt_id")
    op.drop_column("test_attempts", "withheld")
    op.drop_column("test_attempts", "focus_consent")

    op.drop_column("presentations", "dropped")
    op.drop_column("presentations", "time_flag")
    op.drop_column("presentations", "focus_losses")
    op.drop_column("presentations", "paste_events")

    op.execute("UPDATE family_calibrations SET status = 'review' WHERE status = 'compromised'")
    _replace_check("family_calibrations", "family_status", _in("status", STATUSES))
    op.drop_column("family_calibrations", "compromised_at")
    op.drop_column("family_calibrations", "drift_cusum")
