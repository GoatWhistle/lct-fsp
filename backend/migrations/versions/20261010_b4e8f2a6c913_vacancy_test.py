"""Тест по вакансии: план, приложенный к приглашению, и попытка, которая его проходит

План — темы с квотами заданий и требуемый уровень на момент отправки приглашения. Попытка теста
по вакансии ссылается на план; у других попыток ссылки нет.

Revision ID: b4e8f2a6c913
Revises: a7c3e91b5d28
Create Date: 2026-10-10 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b4e8f2a6c913"
down_revision: str | Sequence[str] | None = "a7c3e91b5d28"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PURPOSES = ("determination", "grade_up", "topic_block", "verification")


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _replace_check(table: str, name: str, condition: str) -> None:
    op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, condition)


def upgrade() -> None:
    op.create_table(
        "vacancy_tests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("need_title", sa.String(length=200), nullable=False),
        sa.Column("specialization_code", sa.String(length=32), nullable=False),
        sa.Column("grade_code", sa.String(length=32), nullable=False),
        sa.Column("requirement", sa.Float(), nullable=False),
        sa.Column("topics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["invitation_id"],
            ["invitations.id"],
            name=op.f("fk_vacancy_tests_invitation_id_invitations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["specialization_code"],
            ["specializations.code"],
            name=op.f("fk_vacancy_tests_specialization_code_specializations"),
        ),
        sa.ForeignKeyConstraint(
            ["grade_code"], ["grades.code"], name=op.f("fk_vacancy_tests_grade_code_grades")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vacancy_tests")),
        sa.UniqueConstraint("invitation_id", name=op.f("uq_vacancy_tests_invitation_id")),
    )
    op.add_column("test_attempts", sa.Column("vacancy_test_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_test_attempts_vacancy_test_id_vacancy_tests"),
        "test_attempts",
        "vacancy_tests",
        ["vacancy_test_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        op.f("uq_test_attempts_vacancy_test_id"), "test_attempts", ["vacancy_test_id"]
    )
    _replace_check("test_attempts", "attempt_purpose", _in("purpose", (*PURPOSES, "vacancy_test")))
    op.create_check_constraint(
        op.f("ck_test_attempts_vacancy_test_plan"),
        "test_attempts",
        "(purpose = 'vacancy_test') = (vacancy_test_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_test_attempts_vacancy_test_plan"), "test_attempts", type_="check")
    op.execute("DELETE FROM test_attempts WHERE purpose = 'vacancy_test'")
    _replace_check("test_attempts", "attempt_purpose", _in("purpose", PURPOSES))
    op.drop_constraint(op.f("uq_test_attempts_vacancy_test_id"), "test_attempts", type_="unique")
    op.drop_constraint(
        op.f("fk_test_attempts_vacancy_test_id_vacancy_tests"),
        "test_attempts",
        type_="foreignkey",
    )
    op.drop_column("test_attempts", "vacancy_test_id")
    op.drop_table("vacancy_tests")
