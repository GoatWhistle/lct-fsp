"""Смена грейда: назначение попытки, исход «не прошёл» и журнал категории

Попытка вверх — отдельное измерение, её провал категорию не меняет (исход `not_passed`).
Журнал категории хранит первичное определение и смены грейда: по нему считается правило
ожидания. Уже присвоенные категории переносятся в журнал записью первичного определения.

Revision ID: 5d1e0b7a2c94
Revises: 3f1c9a7d2e64
Create Date: 2026-10-08 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5d1e0b7a2c94"
down_revision: str | Sequence[str] | None = "3f1c9a7d2e64"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "test_attempts",
        sa.Column(
            "purpose",
            sa.Enum(
                "determination",
                "grade_up",
                name="attempt_purpose",
                native_enum=False,
                create_constraint=False,
                length=16,
            ),
            nullable=False,
            server_default="determination",
        ),
    )
    op.alter_column("test_attempts", "purpose", server_default=None)
    op.create_check_constraint(
        op.f("ck_test_attempts_attempt_purpose"),
        "test_attempts",
        "purpose IN ('determination', 'grade_up')",
    )
    op.drop_constraint(op.f("ck_test_attempts_attempt_outcome"), "test_attempts", type_="check")
    op.create_check_constraint(
        op.f("ck_test_attempts_attempt_outcome"),
        "test_attempts",
        "outcome IN ('assigned', 'offered', 'no_category', 'not_passed')",
    )

    op.create_table(
        "category_changes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("specialization_code", sa.String(length=32), nullable=False),
        sa.Column("grade_code", sa.String(length=32), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "determined",
                "up",
                "down",
                name="category_change_kind",
                native_enum=False,
                create_constraint=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('determined', 'up', 'down')",
            name=op.f("ck_category_changes_category_change_kind"),
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["test_attempts.id"],
            name=op.f("fk_category_changes_attempt_id_test_attempts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["grade_code"], ["grades.code"], name=op.f("fk_category_changes_grade_code_grades")
        ),
        sa.ForeignKeyConstraint(
            ["specialization_code"],
            ["specializations.code"],
            name=op.f("fk_category_changes_specialization_code_specializations"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_category_changes_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_category_changes")),
        sa.UniqueConstraint("user_id", "number", name=op.f("uq_category_changes_user_id")),
    )
    op.execute(
        "INSERT INTO category_changes "
        "(id, user_id, number, specialization_code, grade_code, kind, attempt_id, changed_at) "
        "SELECT gen_random_uuid(), user_id, 1, specialization_code, grade_code, 'determined', "
        "attempt_id, assigned_at FROM candidate_categories"
    )


def downgrade() -> None:
    # Незаконченные и непрошедшие попытки вверх прежняя схема не выразит — они удаляются.
    # Прошедшая попытка вверх остаётся: прежний путь читает её как присвоившую категорию, а
    # категория остаётся с текущим грейдом.
    op.drop_table("category_changes")
    op.execute(
        "DELETE FROM test_attempts WHERE purpose = 'grade_up' "
        "AND (outcome IS NULL OR outcome = 'not_passed')"
    )
    op.drop_constraint(op.f("ck_test_attempts_attempt_outcome"), "test_attempts", type_="check")
    op.create_check_constraint(
        op.f("ck_test_attempts_attempt_outcome"),
        "test_attempts",
        "outcome IN ('assigned', 'offered', 'no_category')",
    )
    op.drop_constraint(op.f("ck_test_attempts_attempt_purpose"), "test_attempts", type_="check")
    op.drop_column("test_attempts", "purpose")
