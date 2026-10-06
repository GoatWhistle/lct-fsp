"""Адаптивный тест: калибровка семейств, связка шкалы и оценка темы без ответа

Revision ID: 8adaf94cba66
Revises: 68df9fb9894f
Create Date: 2026-10-06 13:26:22.669975

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "8adaf94cba66"
down_revision: str | Sequence[str] | None = "68df9fb9894f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "family_calibrations",
        sa.Column("family_code", sa.String(length=128), nullable=False),
        sa.Column("discrimination", sa.Double(), nullable=False),
        sa.Column("difficulty", sa.Double(), nullable=False),
        sa.Column("responses", sa.Integer(), nullable=False),
        sa.Column("reference_discrimination", sa.Double(), nullable=True),
        sa.Column("reference_difficulty", sa.Double(), nullable=True),
        sa.Column("refitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "review",
                name="family_status",
                native_enum=False,
                create_constraint=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('active', 'review')", name=op.f("ck_family_calibrations_family_status")
        ),
        sa.PrimaryKeyConstraint("family_code", name=op.f("pk_family_calibrations")),
    )
    op.create_table(
        "scale_links",
        sa.Column("specialization_code", sa.String(length=32), nullable=False),
        sa.Column("before_shift", sa.Double(), nullable=False),
        sa.Column("before_scale", sa.Double(), nullable=False),
        sa.Column("rest_shift", sa.Double(), nullable=False),
        sa.Column("rest_scale", sa.Double(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["specialization_code"],
            ["specializations.code"],
            name=op.f("fk_scale_links_specialization_code_specializations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("specialization_code", name=op.f("pk_scale_links")),
    )
    op.add_column("presentations", sa.Column("topic_theta_rest", sa.Double(), nullable=True))
    op.add_column("presentations", sa.Column("topic_theta_rest_sd", sa.Double(), nullable=True))
    # Бланк попытки больше не список семейств: следующее задание выбирается адаптивно.
    op.drop_column("test_attempts", "blueprint")


def downgrade() -> None:
    op.add_column(
        "test_attempts",
        sa.Column(
            "blueprint",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
    )
    op.drop_column("presentations", "topic_theta_rest_sd")
    op.drop_column("presentations", "topic_theta_rest")
    op.drop_table("scale_links")
    op.drop_table("family_calibrations")
