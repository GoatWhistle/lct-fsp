"""Схемы API пути кандидата. Эталоны, верность ответов и параметры экземпляров сюда не входят:
они живут только на бэкенде."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.controller.schemas import CatalogRef
from app.domain import candidate
from app.domain.attempt import AttemptOutcome, AttemptPurpose, HistoryEvent, Stage
from app.domain.bank import AnswerFormat
from app.domain.candidate import Level
from app.domain.skill import SignalSource


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SurveyIn(BaseModel):
    specialization: str = Field(
        description="Направление — код специализации из `/api/catalog/specializations` с `has_test`"
    )


class AttemptIn(BaseModel):
    grade: str = Field(
        description="Код грейда: заявленный, предложенный для дотеста или, при категории, "
        "следующий выше"
    )


class TopicBlockIn(BaseModel):
    topic: str = Field(description="Код темы из специализации категории")


class AnswerIn(BaseModel):
    presentation_id: uuid.UUID = Field(description="`id` задания из `GET /api/candidate/path/item`")
    response: str = Field(min_length=1, max_length=500)


class SurveyOut(_Out):
    specialization: CatalogRef
    created_at: datetime


class LevelBandOut(BaseModel):
    """Уровень словами (mechanics.md, §4): `low == high` — «уверенно `low`», иначе «между `low`
    и `high`». `null` — ниже порога младшего грейда."""

    low: str | None
    high: str | None
    confident: bool


class LevelOut(BaseModel):
    theta: float = Field(description="Уровень θ, логиты шкалы")
    theta_sd: float = Field(description="Погрешность уровня")
    band: LevelBandOut


class GradeProbabilityOut(BaseModel):
    grade: str
    probability: float = Field(description="P(общий уровень ≥ порог грейда)")


class TestResultOut(BaseModel):
    """Оценка теста определения категории — по ней решается грейд."""

    grade: str = Field(description="Грейд последней попытки")
    overall: LevelOut = Field(description="Общий уровень по специализации")
    grade_probabilities: list[GradeProbabilityOut] = Field(description="От младшего грейда")
    grade_up_hint: str | None = Field(
        description="Грейд выше присвоенного, если стоит попробовать его пройти"
    )


class TopicLevelOut(BaseModel):
    topic: CatalogRef
    level: LevelOut
    sources: list[SignalSource] = Field(
        description="Из каких сигналов сложился уровень: `fsp` — результаты ФСП, `test` — "
        "адаптивный тест; пусто — данных по теме нет"
    )


class SkillProfileOut(BaseModel):
    """Профиль навыков: уровень и погрешность по темам из всех сигналов — так его видит подбор."""

    overall: LevelOut
    topics: list[TopicLevelOut] = Field(description="В порядке тем справочника")
    updated_at: datetime


def level_view(level: Level) -> LevelOut:
    band = level.band
    return LevelOut(
        theta=level.theta,
        theta_sd=level.theta_sd,
        band=LevelBandOut(low=band.low, high=band.high, confident=band.confident),
    )


def skill_profile_view(profile: candidate.SkillProfile) -> SkillProfileOut:
    """Профиль навыков из доменной проекции — уровни словами уже посчитаны."""
    return SkillProfileOut(
        overall=level_view(profile.overall),
        topics=[
            TopicLevelOut(
                topic=CatalogRef.model_validate(t.topic),
                level=level_view(t.level),
                sources=sorted(t.sources),
            )
            for t in profile.topics
        ],
        updated_at=profile.updated_at,
    )


class AttemptProgressOut(BaseModel):
    grade: str
    answered: int
    max_items: int = Field(
        description="Больше заданий попытка не задаст; обычно тест останавливается раньше — "
        "когда уровень определён с нужной точностью"
    )


class TopicBlockOut(BaseModel):
    topic: CatalogRef
    answered: int
    items: int = Field(description="Заданий в блоке — ровно столько, без досрочной остановки")


class CategoryOut(_Out):
    specialization: CatalogRef
    grade: CatalogRef
    assigned_at: datetime


class GradeUpOut(BaseModel):
    grade: str = Field(description="Грейд попытки вверх — следующий после грейда категории")
    available_at: datetime | None = Field(
        description="С какого момента можно начать попытку; `null` — можно сейчас"
    )


class HistoryEntryOut(BaseModel):
    """Строка истории: остановленная попытка (`attempt`) или переход вниз (`step_down`)."""

    at: datetime
    event: HistoryEvent
    grade: str = Field(description="У попытки — её грейд, у перехода — грейд после него")
    purpose: AttemptPurpose | None = Field(
        description="`determination` — первичное определение с каскадом, `grade_up` — попытка "
        "вверх; у перехода — `null`"
    )
    overall: LevelOut | None = Field(description="Уровень по оценке попытки")
    outcome: AttemptOutcome | None = Field(
        description="`assigned` — грейд присвоен; `offered` — предложен дотест; `no_category` — "
        "категории нет; `not_passed` — попытка вверх не прошла, категория прежняя"
    )
    outcome_grade: str | None = Field(description="Присвоенный или предложенный грейд")


class PathOut(BaseModel):
    stage: Stage = Field(
        description="`survey` — опрос; `grade` — выбор грейда; `test` — идёт тест; `offer` — "
        "предложен дотест на `offer_grade`; `category` — категория присвоена; `no_category` — "
        "без категории до `retest_after`"
    )
    survey: SurveyOut | None
    attempt: AttemptProgressOut | None = Field(description="Ход теста на шаге `test`")
    offer_grade: str | None
    retest_after: datetime | None
    category: CategoryOut | None
    result: TestResultOut | None = Field(description="На шагах `offer`, `category`, `no_category`")
    profile: SkillProfileOut | None
    grade_up: GradeUpOut | None = Field(
        description="Попытка на грейд выше — на шаге `category`, если грейд не старший"
    )
    grade_down: str | None = Field(
        description="Грейд для перехода вниз без теста — на шаге `category`, если грейд не младший"
    )
    history: list[HistoryEntryOut] = Field(
        description="Попытки и переходы по времени — на шаге `category`"
    )
    topic_block: TopicBlockOut | None = Field(
        description="Незавершённый блок по теме: задания и ответы — те же `item`, что у теста"
    )


class OptionOut(BaseModel):
    letter: str = Field(description="Буква варианта — её кандидат и отвечает")
    text: str


class ItemOut(BaseModel):
    id: uuid.UUID
    number: int = Field(description="Номер задания в попытке, с 1")
    max_items: int = Field(
        description="Лимит заданий попытки: у теста длина заранее неизвестна, у блока по теме "
        "заданий ровно столько"
    )
    topic_block: bool = Field(description="Задание блока по теме, а не теста")
    topic: CatalogRef
    prompt: str
    code: str | None = Field(description="Листинг, таблица или граф к условию — моноширинно")
    answer_format: AnswerFormat = Field(
        description="`value` — ответ вводится текстом; `choice` — буква одного варианта; "
        "`ordering` — буквы всех вариантов в верном порядке строкой, например «KBXF»"
    )
    options: list[OptionOut] = Field(
        description="Варианты по алфавиту букв; буквы и порядок текстов свои у каждого экземпляра"
    )
