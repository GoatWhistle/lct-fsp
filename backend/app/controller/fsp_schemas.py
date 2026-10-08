"""Схемы API ФСП ID и достижений ФСП."""

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field

from app.controller.schemas import CatalogRef
from app.domain.fsp import FspIntent, FspResult

RESULT_DESCRIPTION = (
    "`winner` — победитель, `prize` — призёр, `finalist` — финалист, `participant` — участник "
    "отбора: факт в профиле, не свидетельство уровня"
)


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class FspAuthorizeIn(BaseModel):
    intent: FspIntent = Field(
        description="`login` — войти или зарегистрироваться кандидатом, `link` — привязать ФСП "
        "ID к своей учётке кандидата (нужен вход)"
    )


class FspAuthorizeOut(BaseModel):
    authorization_url: str = Field(description="Куда отправить браузер — страница входа ФСП ID")


class FspAchievementOut(_Out):
    """Подтверждённое достижение ФСП — полностью: самому кандидату, в PDF и работодателю после
    раскрытия."""

    event: str = Field(description="Мероприятие")
    date: dt.date
    discipline: CatalogRef
    place: int | None = Field(description="Место; `null` — реестр его не знает")
    result: FspResult = Field(description=RESULT_DESCRIPTION)
    team_role: CatalogRef | None = Field(
        description="Роль в команде — специализация; `null` — личный зачёт или роль не указана"
    )


class FspAnonymizedAchievementOut(_Out):
    """Достижение в обезличенной карточке: только тип результата, дисциплина и год."""

    result: FspResult = Field(description=RESULT_DESCRIPTION)
    discipline: CatalogRef
    year: int


class FspDivergenceOut(_Out):
    """Тест по теме ниже уровня результата ФСП больше чем на `fsp_divergence_theta`. Видит только
    кандидат; на профиль и подбор не влияет."""

    topic: CatalogRef
    discipline: CatalogRef
    event: str
    result: FspResult
    result_level: float = Field(description="Уровень, который подтверждает результат, θ")
    test_level: float = Field(description="Уровень по теме по оценке теста, θ")


class FspStatusOut(BaseModel):
    linked: bool = Field(description="ФСП ID привязан")
    fsp_id: str | None
    can_unlink: bool = Field(
        description="Отвязать можно: у учётки есть пароль. Учётка, созданная через ФСП ID, входит "
        "только через него"
    )
    fetched_at: dt.datetime | None = Field(
        description="Когда достижения получены из реестра; `null` — реестр ещё не ответил"
    )
    achievements: list[FspAchievementOut] = Field(
        description="Подтверждённые достижения; пусто — нет истории ФСП"
    )
    divergences: list[FspDivergenceOut] = Field(
        description="Расхождения ФСП и теста — рекомендация пройти проверочный блок, без штрафа"
    )
