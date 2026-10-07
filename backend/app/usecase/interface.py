"""Порты — всё, что можно заменить другой реализацией (docs/adr/0001-layers-and-ports.md).

Типы портов — из `app.domain`; реализации — в `app.adapter` и `app.repository`, сборка — в
`backend/main.py`.
"""

from collections.abc import Iterable
from datetime import datetime
from typing import Protocol

from app.domain.candidate import ProfileSheet
from app.domain.mail import Mail
from app.domain.skill import Observation, Prior, SkillEstimate


class SkillModel(Protocol):
    """Модель навыка (mechanics.md, §3): уровень по темам из априорного и наблюдений.

    Сейчас — IRT 2PL с иерархическим априорным, модуль `app.skills.irt`. Оценка детерминирована:
    те же априорное и наблюдения в том же порядке дают ту же оценку.
    """

    def initial(self, prior: Prior) -> SkillEstimate:
        """Оценка без наблюдений — только по априорному."""
        ...

    def estimate(self, prior: Prior, observations: Iterable[Observation]) -> SkillEstimate:
        """Оценка по априорному и упорядоченным наблюдениям."""
        ...


class Mailer(Protocol):
    """Почта — внешняя система. Отправка не роняет сценарий: письмо, которое не ушло,
    кандидат запрашивает повторно."""

    def send(self, mail: Mail) -> None: ...


class ProfilePdfRenderer(Protocol):
    """Рендер PDF-профиля. Показывает проекцию как есть: что в неё попало, решил сценарий."""

    def render(self, sheet: ProfileSheet, *, now: datetime) -> bytes:
        """PDF; `now` — дата формирования в подвале и метаданных."""
        ...
