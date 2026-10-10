"""Метка доверия компании: домен сайта, подтверждённый письмом на адрес этого домена

Компания помнит подтверждённый домен и когда; ссылки подтверждения — хэш токена со сроком.

Revision ID: c6d1a9e4f357
Revises: b4e8f2a6c913
Create Date: 2026-10-10 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c6d1a9e4f357"
down_revision: str | Sequence[str] | None = "b4e8f2a6c913"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("verified_domain", sa.String(length=253), nullable=True))
    op.add_column(
        "companies", sa.Column("domain_verified_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_table(
        "company_domain_verifications",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("domain", sa.String(length=253), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["companies.user_id"],
            name=op.f("fk_company_domain_verifications_user_id_companies"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("token_hash", name=op.f("pk_company_domain_verifications")),
    )
    op.create_index(
        op.f("ix_company_domain_verifications_user_id"),
        "company_domain_verifications",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_company_domain_verifications_user_id"), table_name="company_domain_verifications"
    )
    op.drop_table("company_domain_verifications")
    op.drop_column("companies", "domain_verified_at")
    op.drop_column("companies", "verified_domain")
