"""Переписка в принятом приглашении и отзыв доступа к данным кандидата

У приглашения — время отзыва доступа; у существующих его нет. Сообщения — по приглашению, с
автором-стороной и отметкой о прочтении другой стороной.

Revision ID: c4a7e91d2f60
Revises: b7e2c4d91f3a
Create Date: 2026-10-08 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4a7e91d2f60"
down_revision: str | Sequence[str] | None = "b7e2c4d91f3a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("invitations", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "invitation_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column(
            "author",
            sa.Enum(
                "candidate",
                "employer",
                name="message_author",
                native_enum=False,
                create_constraint=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "author IN ('candidate', 'employer')",
            name=op.f("ck_invitation_messages_message_author"),
        ),
        sa.ForeignKeyConstraint(
            ["invitation_id"],
            ["invitations.id"],
            name=op.f("fk_invitation_messages_invitation_id_invitations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invitation_messages")),
        sa.UniqueConstraint("seq", name=op.f("uq_invitation_messages_seq")),
    )
    op.create_index(
        "ix_invitation_messages_invitation_id_seq",
        "invitation_messages",
        ["invitation_id", "seq"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_invitation_messages_invitation_id_seq", table_name="invitation_messages")
    op.drop_table("invitation_messages")
    op.drop_column("invitations", "revoked_at")
