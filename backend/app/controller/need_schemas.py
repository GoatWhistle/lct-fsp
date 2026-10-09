"""Схемы API потребности и подборки."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.controller.salary import SALARY_UNIT, Salary, SalaryBasisOut
from app.controller.schemas import CatalogRef, GradeStatusOut
from app.domain.candidate import GradeStatusKind
from app.domain.importance import TopicImportance
from app.domain.match import Verdict
from app.domain.need_draft import DraftField
from app.domain.selection import SelectionBlock
from app.domain.work import WorkFormat

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class TopicImportanceIn(BaseModel):
    specialization: str = Field(description="Код специализации из `/api/catalog/specializations`")
    stack: list[str] = Field(
        default_factory=list,
        max_length=50,
        description="Коды технологий из `/api/catalog/technologies` — любые из справочника",
    )
    topic_importance: dict[str, TopicImportance] = Field(
        default_factory=dict,
        description="Правки важности: код темы специализации → важность. Темы без правки получают "
        "важность из стека",
    )


class NeedIn(TopicImportanceIn):
    title: Title = Field(description="Кого ищете")
    team_description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] = (
        Field(default="", description="Чем занимается команда")
    )
    grade: str = Field(description="Код грейда из `/api/catalog/grades`")
    work_format: WorkFormat
    city: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None = Field(
        default=None, description="Обязателен для офиса и гибрида"
    )
    salary_from: Salary | None = Field(
        default=None,
        description=f"{SALARY_UNIT}. Вилка необязательна; если указана — обе границы больше "
        "нуля, «от» не больше «до»",
    )
    salary_to: Salary | None = Field(default=None, description=SALARY_UNIT)


class NeedTextIn(BaseModel):
    text: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20000)
    ] = Field(description="Текст вакансии или описание потребности как есть")


class NeedDraftOut(SalaryBasisOut):
    """Черновик «система поняла так»: только значения справочника. Ничего не сохранено —
    работодатель правит поля и строит подборку (`POST /api/employer/selections`) или заводит
    потребность (`POST /api/employer/needs`). Важность тем — из стека, как у формы."""

    kind: Literal["draft"]
    title: str | None = Field(description="Кого ищете — первая строка текста, если похожа")
    specialization: CatalogRef | None
    grade: CatalogRef | None
    stack: list[CatalogRef] = Field(description="В порядке справочника")
    work_format: WorkFormat | None
    city: str | None
    salary_from: int | None = Field(description=f"{SALARY_UNIT}. Может быть без «до»")
    salary_to: int | None = Field(description=f"{SALARY_UNIT}. Может быть без «от»")
    confidence: dict[DraftField, float | None] = Field(
        description="Уверенность по распознанным полям в [0, 1]; `null` — разбор её не считает. "
        "Нераспознанных полей здесь нет"
    )
    uncertain: list[DraftField] = Field(
        description="Распознанные поля с уверенностью ниже `need_draft_confident` — проверьте их"
    )


class OutOfCatalogOut(BaseModel):
    """Такой специализации на платформе нет: что просили и ближайшие специализации справочника."""

    kind: Literal["out_of_catalog"]
    asked: str = Field(description="Что просили, например «1С» или «Геймдев»")
    nearest: list[CatalogRef] = Field(
        min_length=1, description="Ближайшие специализации — не пусто"
    )


NeedParseOut = Annotated[NeedDraftOut | OutOfCatalogOut, Field(discriminator="kind")]


class TopicImportanceOut(BaseModel):
    topic: CatalogRef
    importance: TopicImportance = Field(
        description="`key` — ключевая, `important` — важная, `nice` — желательная"
    )
    edited: bool = Field(description="Важность поставил работодатель, а не вывод из стека")
    technologies: list[CatalogRef] = Field(description="Технологии стека, связанные с темой")


class NeedOut(SalaryBasisOut):
    id: uuid.UUID
    title: str
    team_description: str
    specialization: CatalogRef
    grade: CatalogRef
    stack: list[CatalogRef] = Field(description="По названию технологии")
    work_format: WorkFormat
    city: str | None
    salary_from: int | None = Field(description=SALARY_UNIT)
    salary_to: int | None = Field(description=SALARY_UNIT)
    topics: list[TopicImportanceOut] = Field(description="Все темы специализации по порядку")
    created_at: datetime
    updated_at: datetime


class RequirementOut(BaseModel):
    topic: CatalogRef
    importance: TopicImportance
    edited: bool = Field(description="Важность поставил работодатель, а не вывод из стека")
    weight: float = Field(description="Вес темы в скоре: вес важности, нормированный на сумму")
    requirement: float = Field(description="Требуемый уровень θ — порог грейда потребности")


class NeedSnapshot(SalaryBasisOut):
    """Потребность на момент построения подборки — с весами и требованиями по темам."""

    title: str
    specialization: CatalogRef
    grade: CatalogRef
    stack: list[CatalogRef]
    work_format: WorkFormat
    city: str | None
    salary_from: int | None = Field(description=SALARY_UNIT)
    salary_to: int | None = Field(description=SALARY_UNIT)
    topics: list[RequirementOut] = Field(description="Все темы специализации по порядку")
    updated_at: datetime = Field(description="Версия потребности, по которой построена подборка")


class CategoryFilterIn(BaseModel):
    specialization: str = Field(description="Код специализации")
    grade: str = Field(description="Код грейда")


class CandidateFiltersIn(BaseModel):
    """Фильтры кандидатов — одни для поиска по банку и уточнения подборки. Все необязательны,
    вместе — пересечение условий; пустой объект не сужает ничего."""

    specialization: str | None = Field(
        default=None,
        description="Код специализации: категории, без неё — заявленного грейда",
    )
    grade: str | None = Field(
        default=None,
        description="Код грейда, по которому кандидат в выдаче: категории, без неё — заявленный",
    )
    category: CategoryFilterIn | None = Field(
        default=None, description="Категория по тесту — неподтверждённый грейд её не даёт"
    )
    stack: list[str] = Field(
        default_factory=list,
        max_length=50,
        description="Коды технологий: в самоописанном стеке есть хотя бы одна",
    )
    fsp_confirmed: bool = Field(
        default=False, description="Только с подтверждёнными достижениями ФСП"
    )
    confident: bool = Field(
        default=False,
        description="Только с уверенным уровнем: погрешность общего уровня профиля не выше "
        "`search_confident_sd`. Без категории профиля нет — не проходит",
    )
    grade_status: list[GradeStatusKind] = Field(
        default_factory=list, description="Статус грейда — любой из перечисленных"
    )


class CandidateFiltersOut(CandidateFiltersIn):
    """Применённые фильтры — те же поля, что на входе."""


class TopicFitOut(BaseModel):
    topic: CatalogRef
    importance: TopicImportance
    weight: float = Field(description="Вес темы в скоре")
    requirement: float = Field(description="Требуемый уровень θ")
    theta: float = Field(description="Уровень по профилю навыков")
    theta_sd: float = Field(description="Погрешность уровня")
    probability: float = Field(description="P(уровень ≥ требование)")
    contribution: float = Field(description="Вклад в соответствие: (1 − λ) · вес · вероятность")
    verdict: Verdict = Field(
        description="`confidently_above` — уверенно выше требования, `likely_above` — скорее "
        "выше, `likely_below` — скорее ниже, `below` — ниже требования"
    )
    low_data: bool = Field(description="Погрешность выше `topic_low_data_sd` — данных мало")
    regular_task: bool = Field(
        description="Источник уверенности: уровень по теме подтверждён регулярным заданием"
    )
    fsp_confirmed: bool = Field(
        description="Уровень подтверждён результатом ФСП — к формулировке «подтверждено ФСП»"
    )
    verification_confirmed: bool = Field(
        description="Уровень категории подтверждён проверочным блоком, и его задания были по "
        "теме — к формулировке «подтверждено проверочным блоком»"
    )


class StackFitOut(BaseModel):
    matched: list[CatalogRef] = Field(
        description="Технологии потребности в самоописании кандидата — не подтверждены"
    )
    total: int = Field(description="Технологий в стеке потребности")
    overlap: float = Field(description="Доля технологий потребности в самоописании, o")
    contribution: float | None = Field(
        description="Вклад самоописания: λ · o, не больше λ; `null` — нижний блок, скора нет"
    )


AcceptanceFactor = Literal["salary", "grade", "format", "city", "load", "match", "industry"]


class AcceptanceFactorOut(BaseModel):
    factor: AcceptanceFactor
    contribution: float = Field(
        description="Вклад фактора в логит P: положительный повышает P, отрицательный снижает"
    )


class AcceptanceExplanationOut(BaseModel):
    """Вклады точно аддитивны в логите: `base` плюс сумма вкладов равна `logit`, а P — его
    сигмоида. Ожидания кандидата здесь нет, только вклад вилки в P."""

    base: float = Field(description="Логит P при средних признаках обучения")
    logit: float = Field(description="Логит P(принятия) строки")
    factors: list[AcceptanceFactorOut]


class SalaryHintOut(SalaryBasisOut):
    available: bool = Field(
        description="`false` — P нет (нет файла модели, у потребности не было вилки, кандидат "
        "в нижнем блоке): ни вероятности, ни подсказки"
    )
    probability: float | None = Field(
        description="P(принятия) при вилке работодателя, округлённой до шага подсказки"
    )
    evaluated_from: Salary | None = Field(description="«От» вилки, по которой посчитана P")
    evaluated_to: Salary | None = Field(description="«До» вилки, по которой посчитана P")
    target_probability: float | None = Field(description="Целевая P(принятия)")
    reachable: bool = Field(
        description="Есть ли вилка, при которой P достигает цели, в пределах сетки подсказки"
    )
    hint_from: Salary | None = Field(
        description="«От» самой низкой вилки сетки с P не ниже цели; кратно шагу округления; "
        "`null` — цель недостижима"
    )
    hint_to: Salary | None = Field(description="«До» той же вилки; кратно шагу округления")
    rounding: int | None = Field(description="Шаг округления вилки в подсказке, ₽")


class SelectionEntryOut(BaseModel):
    """Кандидат в подборке — обезличенно: место, статус грейда, соответствие и его объяснение.
    Карточка — `GET /api/employer/candidates/{candidate_id}`."""

    candidate_id: uuid.UUID
    position: int = Field(
        description="Место в общей выдаче с 1: сначала точные, затем близкие, затем "
        "неподтверждённые"
    )
    block: SelectionBlock = Field(
        description="`exact` — категория совпадает с потребностью, `nearby` — соседний грейд, "
        "`unconfirmed` — категории нет, заявлен грейд потребности"
    )
    rank: int = Field(description="Место внутри блока с 1")
    grade: CatalogRef = Field(
        description="Грейд категории кандидата; в блоке `unconfirmed` — заявленный"
    )
    grade_status: GradeStatusOut
    match_score: float | None = Field(
        description="Соответствие — сумма вкладов тем и стека; `null` — блок `unconfirmed`: "
        "скора по темам нет"
    )
    acceptance_probability: float | None = Field(
        description="P(принятия); `null` — модели принятия ещё нет, множитель 1, или блок "
        "`unconfirmed`"
    )
    mutual_score: float | None = Field(
        description="Соответствие × P(принятия) — по нему порядок; `null` — блок `unconfirmed`: "
        "порядок по доле стека потребности в самоописании"
    )
    topics: list[TopicFitOut] = Field(
        description="Вклады тем в порядке тем специализации; в блоке `unconfirmed` — пусто"
    )
    stack: StackFitOut
    stale: bool = Field(description="Давно не подтверждал уровень: сигналов не было дольше срока")
    acceptance_explanation: AcceptanceExplanationOut | None = Field(
        description="SHAP-объяснение P(принятия); `null` — P нет"
    )


class SelectionSummaryOut(BaseModel):
    id: uuid.UUID
    need_id: uuid.UUID | None = Field(
        description="`null` — потребность удалена или подборка построена по черновику"
    )
    title: str = Field(description="Кого ищете — из снимка потребности")
    specialization: CatalogRef
    grade: CatalogRef
    exact_total: int = Field(description="Кандидатов с категорией потребности")
    nearby_total: int = Field(description="Близких — соседнего грейда")
    unconfirmed_total: int = Field(
        description="Без категории, заявивших грейд потребности, — нижний блок"
    )
    created_at: datetime


class SelectionOut(SelectionSummaryOut):
    need: NeedSnapshot
    stack_cap: float = Field(description="λ — потолок вклада самоописания на момент построения")
    offset: int
    filters: CandidateFiltersOut = Field(
        description="Последние применённые фильтры: открытие подборки отдаёт выдачу через них"
    )
    filtered_exact_total: int = Field(description="Точных после фильтров")
    filtered_nearby_total: int = Field(description="Близких после фильтров")
    filtered_unconfirmed_total: int = Field(description="Нижнего блока после фильтров")
    shortlist: list[uuid.UUID] = Field(
        description="Шортлист в порядке выдачи — от фильтров не зависит"
    )
    entries: list[SelectionEntryOut] = Field(
        description="Страница выдачи после фильтров с `offset + 1`-й строки; места и ранги — "
        "исходные, без фильтров — вся выдача"
    )


class ShortlistOut(BaseModel):
    selection_id: uuid.UUID
    entries: list[SelectionEntryOut] = Field(
        description="Отмеченные кандидаты в порядке выдачи, без фильтров подборки"
    )


class SearchHitOut(BaseModel):
    """Кандидат в поиске — обезличенно, как в подборке. Карточка —
    `GET /api/employer/candidates/{candidate_id}`."""

    candidate_id: uuid.UUID
    position: int = Field(
        description="Место в выдаче с 1: сначала с категорией, затем — с неподтверждённым грейдом"
    )
    specialization: str = Field(
        description="Код специализации категории, без неё — заявленного грейда"
    )
    grade_status: GradeStatusOut
    theta: float | None = Field(
        description="Общий уровень по профилю навыков на «сейчас»; `null` — категории нет, "
        "профиля навыков тоже"
    )
    theta_sd: float | None = Field(description="Погрешность общего уровня")
    grade_probability: float | None = Field(
        description="P(общий уровень ≥ порог грейда категории) — по ней порядок; `null` — "
        "категории нет"
    )
    fsp_confirmed: bool = Field(description="Есть подтверждённые достижения ФСП")


class SearchOut(BaseModel):
    filters: CandidateFiltersOut
    total: int = Field(description="Найдено всего")
    unconfirmed_total: int = Field(description="Из них — с неподтверждённым грейдом")
    offset: int
    entries: list[SearchHitOut] = Field(description="Страница выдачи с места `offset + 1`")
