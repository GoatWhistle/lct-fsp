"""ФСП ID и достижения ФСП: привязка к учётке, снимок реестра, дисциплины, источники тем профиля

Учётка, созданная входом через ФСП ID, — без пароля. Темы профиля навыков помнят уровни доверия
своих наблюдений; профили до этой ревизии построены только по тесту — источник «тест» получают
темы, по которым кандидат отвечал. Объяснение в сохранённых подборках получает у темы
`fsp_confirmed`: до ФСП подтверждённых им тем не было.

Revision ID: 5abf1dffb9d7
Revises: 7c604420b704
Create Date: 2026-10-08 09:47:42.288262

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "5abf1dffb9d7"
down_revision: str | Sequence[str] | None = "7c604420b704"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fsp_disciplines",
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_fsp_disciplines")),
    )
    op.create_table(
        "fsp_snapshots",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_fsp_snapshots_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_fsp_snapshots")),
    )
    op.create_table(
        "fsp_achievements",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("event", sa.String(length=255), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("discipline_code", sa.String(length=32), nullable=False),
        sa.Column("place", sa.Integer(), nullable=True),
        sa.Column(
            "result",
            sa.Enum(
                "winner",
                "prize",
                "finalist",
                "participant",
                name="fsp_result",
                native_enum=False,
                create_constraint=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("team_role", sa.String(length=32), nullable=True),
        sa.CheckConstraint(
            "result IN ('winner', 'prize', 'finalist', 'participant')",
            name=op.f("ck_fsp_achievements_fsp_result"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["fsp_snapshots.user_id"],
            name=op.f("fk_fsp_achievements_user_id_fsp_snapshots"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "position", name=op.f("pk_fsp_achievements")),
    )
    op.create_table(
        "fsp_discipline_topics",
        sa.Column("discipline_code", sa.String(length=32), nullable=False),
        sa.Column("topic_code", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["discipline_code"],
            ["fsp_disciplines.code"],
            name=op.f("fk_fsp_discipline_topics_discipline_code_fsp_disciplines"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["topic_code"],
            ["topics.code"],
            name=op.f("fk_fsp_discipline_topics_topic_code_topics"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "discipline_code", "topic_code", name=op.f("pk_fsp_discipline_topics")
        ),
    )
    op.add_column(
        "skill_profile_topics",
        sa.Column(
            "sources",
            postgresql.ARRAY(sa.String(length=16)),
            server_default="{}",
            nullable=False,
        ),
    )
    op.execute(
        """
        UPDATE skill_profile_topics AS t SET sources = ARRAY['test']
        FROM skill_profiles AS p
        WHERE p.id = t.profile_id AND EXISTS (
            SELECT 1 FROM presentations AS s
            JOIN test_attempts AS a ON a.id = s.attempt_id
            WHERE a.user_id = p.user_id
              AND a.specialization_code = p.specialization_code
              AND s.topic_code = t.topic_code
              AND s.answered_at IS NOT NULL
        )
        """
    )
    _explanation_topics("t || '{\"fsp_confirmed\": false}'::jsonb")
    op.add_column("users", sa.Column("fsp_id", sa.String(length=255), nullable=True))
    op.alter_column("users", "password_hash", existing_type=sa.VARCHAR(length=255), nullable=True)
    op.create_unique_constraint(op.f("uq_users_fsp_id"), "users", ["fsp_id"])


def downgrade() -> None:
    op.drop_constraint(op.f("uq_users_fsp_id"), "users", type_="unique")
    # Учётки без пароля входят только через ФСП ID — без него им не войти.
    op.execute("DELETE FROM users WHERE password_hash IS NULL")
    op.alter_column("users", "password_hash", existing_type=sa.VARCHAR(length=255), nullable=False)
    op.drop_column("users", "fsp_id")
    op.drop_column("skill_profile_topics", "sources")
    _explanation_topics("t - 'fsp_confirmed'")
    op.drop_table("fsp_discipline_topics")
    op.drop_table("fsp_achievements")
    op.drop_table("fsp_snapshots")
    op.drop_table("fsp_disciplines")


def _explanation_topics(change: str) -> None:
    """Правка каждой темы объяснения сохранённых подборок: `t` — тема, JSONB."""
    op.execute(
        f"""
        UPDATE selection_entries SET explanation = jsonb_set(
            explanation,
            '{{topics}}',
            (SELECT coalesce(jsonb_agg({change}), '[]'::jsonb)
             FROM jsonb_array_elements(explanation -> 'topics') AS t)
        )
        """
    )
