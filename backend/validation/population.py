"""Синтетический рынок D1 и D2 плана валидации: кандидаты со скрытой истиной и персонажами,
работодатели, потребности и размеченные пары (docs/validation-plan.md, «Данные»).

Порядок порождения — только от истины к наблюдаемому: истина кандидата → самоописание, ответы и
время, достижения ФСП. Эталонная релевантность пары — из истины кандидата и потребности
(`validation.truth.relevance`). Файлы набора разложены так, чтобы это было видно и в каталоге:

- `truth/` — истина: кандидаты, параметры семейств, позиция вилок работодателей;
- `observed/` — что видит платформа: опрос, самоописание, ответы и время, реестр ФСП;
- `needs.jsonl` — вход работодателей; `pairs.jsonl` — эталон пар «потребность — кандидат».

Код оценки и подбора читает только `observed/` и `needs.jsonl`; `truth/` читают генератор и
разметка (`label_files`). Тот же seed — те же файлы байт в байт: случайность идёт из потоков
`random.Random` с именем, а не из порядка вызовов в разных частях генератора.

Реализм — из открытых данных, источник у каждой таблицы ниже.
"""

import enum
import json
import math
import random
import uuid
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import fsp_stub
from app.adapter.catalog_file import load_catalog
from app.adapter.code_runner import InProcessCodeRunner
from app.domain.bank import families_for_topics
from app.domain.calibration import Parameters
from app.domain.determination import grades_by_threshold
from app.domain.importance import TopicImportance
from app.domain.need import NeedForm, need_content, need_terms
from app.domain.selection import NeedSnapshot, need_snapshot
from app.domain.work import WorkFormat
from app.usecase.skill_profile import specialization_prior
from settings import CATALOG_FILE, Mechanics
from validation.main import Catalog
from validation.market import SEED, Candidate, expert, true_parameters
from validation.truth import (
    CandidateTruth,
    Persona,
    Response,
    ResponseModel,
    guessing,
    relevance,
    respond,
)

D1_SEED = SEED
D2_SEED = 20261006
# Время, на которое собраны потребности набора: от него не зависит ничего, кроме поля версии.
NOW = datetime(2026, 1, 1, tzinfo=UTC)

# Медианы зарплат по квалификации, ₽ в месяц на руки: «Хабр Карьера», калькулятор зарплат,
# https://career.habr.com/salaries, 41 243 анкеты, открыто 2026-10-08. Калькулятор собирает
# зарплату на руки (https://habr.com/ru/post/708198), платформа считает до НДФЛ — пересчёт по
# ставке 13 %.
SALARY_NET_MEDIAN = {"intern": 64_000, "junior": 88_000, "middle": 167_000, "senior": 288_000}
NDFL = 0.13
SALARY_ROUNDING = 5_000

# Доля разработчиков, работающих с технологией, %: Stack Overflow Developer Survey 2025,
# раздел Technology, все респонденты, https://survey.stackoverflow.co/2025/technology/, открыто
# 2026-10-08. Технологий справочника, которых нет в опубликованных таблицах опроса, —
# в `USAGE_ESTIMATED`: это оценка команды, а не данные.
USAGE = {
    "javascript": 66.0,
    "html-css": 61.9,
    "python": 57.9,
    "bash": 48.7,
    "typescript": 43.6,
    "java": 29.4,
    "csharp": 27.8,
    "go": 16.4,
    "kotlin": 10.8,
    "postgresql": 55.6,
    "mysql": 40.5,
    "redis": 28.0,
    "clickhouse": 2.4,
    "nodejs": 48.7,
    "react": 44.7,
    "angular": 18.2,
    "vue": 17.6,
    "django": 12.6,
    "fastapi": 14.8,
    "spring": 14.7,
    "docker": 71.1,
    "kubernetes": 28.5,
    "terraform": 17.8,
    "ansible": 11.7,
    "prometheus": 11.8,
    "vite": 25.4,
}
USAGE_ESTIMATED = {
    "linux": 50.0,
    "nginx": 25.0,
    "kafka": 15.0,
    "rabbitmq": 12.0,
    "pytest": 20.0,
    "jest": 20.0,
    "playwright": 12.0,
    "selenium": 10.0,
    "postman": 30.0,
    "jmeter": 5.0,
    "k6": 3.0,
    "pandas": 25.0,
    "numpy": 25.0,
    "scikit-learn": 12.0,
    "catboost": 3.0,
    "pytorch": 10.0,
    "spark": 6.0,
    "airflow": 5.0,
    "mlflow": 3.0,
    "gitlab-ci": 20.0,
    "github-actions": 30.0,
    "grafana": 15.0,
}

# Сочетаемость стека: экосистема специализации — ядро, которое идёт вместе (язык и его
# фреймворк), вес — доля языка или фреймворка в опросе выше; к ядру — дополнения специализации,
# каждое с вероятностью своей доли.
ECOSYSTEMS: dict[str, tuple[tuple[tuple[str, ...], float], ...]] = {
    "backend": (
        (("python", "fastapi"), USAGE["fastapi"]),
        (("python", "django"), USAGE["django"]),
        (("java", "spring"), USAGE["java"]),
        (("kotlin", "spring"), USAGE["kotlin"]),
        (("go",), USAGE["go"]),
        (("csharp",), USAGE["csharp"]),
        (("nodejs", "typescript"), USAGE["nodejs"]),
    ),
    "frontend": (
        (("typescript", "html-css", "react"), USAGE["react"]),
        (("typescript", "html-css", "angular"), USAGE["angular"]),
        (("javascript", "html-css", "vue"), USAGE["vue"]),
    ),
    "data-ml": ((("python", "pandas", "numpy"), USAGE["python"]),),
    "qa": (
        (("python", "pytest"), USAGE["python"]),
        (("java", "selenium"), USAGE["java"]),
        (("javascript", "playwright"), USAGE["javascript"]),
    ),
    "devops": (
        (("linux", "bash"), USAGE["bash"]),
        (("linux", "bash", "python"), USAGE["python"]),
        (("linux", "bash", "go"), USAGE["go"]),
    ),
}
ADDONS: dict[str, tuple[str, ...]] = {
    "backend": ("postgresql", "mysql", "redis", "kafka", "rabbitmq", "docker"),
    "frontend": ("vite", "jest", "playwright"),
    "data-ml": (
        "scikit-learn",
        "catboost",
        "pytorch",
        "postgresql",
        "clickhouse",
        "spark",
        "airflow",
        "mlflow",
        "docker",
    ),
    "qa": ("postman", "postgresql", "mysql", "jmeter", "k6", "docker"),
    "devops": (
        "docker",
        "kubernetes",
        "terraform",
        "ansible",
        "prometheus",
        "grafana",
        "gitlab-ci",
        "github-actions",
        "nginx",
    ),
}
ROLE = {
    "backend": "бэкенд-разработчик",
    "frontend": "фронтенд-разработчик",
    "data-ml": "специалист по данным и ML",
    "qa": "инженер по тестированию",
    "devops": "DevOps-инженер",
}
# Города и форматы — оценка команды: в открытых данных выше их сочетания нет.
CITIES = (
    ("Москва", 0.45),
    ("Санкт-Петербург", 0.2),
    ("Казань", 0.09),
    ("Новосибирск", 0.09),
    ("Екатеринбург", 0.09),
    ("Нижний Новгород", 0.08),
)
CANDIDATE_FORMATS = (
    ((WorkFormat.remote,), 0.35),
    ((WorkFormat.hybrid, WorkFormat.remote), 0.25),
    ((WorkFormat.office, WorkFormat.hybrid), 0.2),
    ((WorkFormat.office, WorkFormat.hybrid, WorkFormat.remote), 0.2),
)
NEED_FORMATS = ((WorkFormat.remote, 0.4), (WorkFormat.hybrid, 0.4), (WorkFormat.office, 0.2))
# Личные данные резюме — только для базовых линий по тексту и двойников M5: оценка и подбор их не
# видят. Имена и вузы — оценка команды, частые имена и фамилии и известные вузы.
MALE_NAMES = ("Александр", "Дмитрий", "Максим", "Иван", "Артём", "Никита", "Михаил", "Егор")
FEMALE_NAMES = ("Анна", "Мария", "Елена", "Дарья", "Анастасия", "Екатерина", "Полина", "Ольга")
# Мужская форма; женская — с «а» на конце.
SURNAMES = ("Иванов", "Смирнов", "Кузнецов", "Попов", "Соколов", "Лебедев", "Козлов", "Новиков")
LEADING_UNIVERSITIES = ("МГУ имени М. В. Ломоносова", "МФТИ", "НИУ ВШЭ", "Университет ИТМО")
REGIONAL_UNIVERSITIES = (
    "Курганский государственный университет",
    "Вятский государственный университет",
    "Череповецкий государственный университет",
    "Тувинский государственный университет",
)
# Возраст — 21 год плюс стаж плюс сдвиг группы: младшие — 0–3 года, старшие — 14–18 лет. Граница
# групп — `OLDER_FROM`.
AGE_SHIFT = {False: (0, 3), True: (14, 18)}
OLDER_FROM = 35
EXPERIENCE_YEARS = {
    None: (0, 0),
    "intern": (0, 1),
    "junior": (1, 2),
    "middle": (3, 5),
    "senior": (6, 10),
}


class SalaryPosition(enum.StrEnum):
    """Где вилка работодателя относительно рынка грейда."""

    below = "below"
    market = "market"
    above = "above"


@dataclass(frozen=True)
class GeneratorParams:
    """Числа генератора набора. Сиды, размеры и доли персонажей и вилок — из плана валидации,
    остальные — строки раздела «Синтетический рынок» в parameters.md под этими же именами."""

    name: str
    seed: int
    candidates_per_specialization: int = 600
    employers: int = 50
    needs_per_specialization: int = 20
    persona_shares: tuple[tuple[Persona, float], ...] = (
        (Persona.honest, 0.7),
        (Persona.resume_inflator, 0.1),
        (Persona.bank_leak, 0.1),
        (Persona.llm_helper, 0.1),
    )
    salary_position_shares: tuple[tuple[SalaryPosition, float], ...] = (
        (SalaryPosition.below, 0.3),
        (SalaryPosition.market, 0.4),
        (SalaryPosition.above, 0.3),
    )
    # Центр вилки — медиана грейда, умноженная на множитель позиции.
    salary_position_factor: tuple[tuple[SalaryPosition, float], ...] = (
        (SalaryPosition.below, 0.75),
        (SalaryPosition.market, 1.0),
        (SalaryPosition.above, 1.3),
    )
    # θ*_s — смесь нормальных: (вес, среднее, sd).
    common_modes: tuple[tuple[float, float, float], ...] = ((1.0, 0.0, 1.2),)
    # sd(δ*) — отклонения тем от общей части.
    topic_sd: float = 0.7
    # Заявка относительно истинного грейда: тот же, на один выше, на один ниже.
    claimed_shift_weights: tuple[float, float, float] = (0.6, 0.25, 0.15)
    # sd личной скорости — сдвига ln T.
    speed_sd: float = 0.3
    salary_scale: float = 1.0
    # sd ln ожидаемой зарплаты кандидата вокруг медианы его грейда.
    salary_sd: float = 0.25
    # sd ln центра вилки потребности и полуширина вилки — доля центра.
    need_salary_sd: float = 0.1
    need_salary_spread: float = 0.15
    # Доля потребностей, где работодатель сам сделал одну тему ключевой.
    need_edited_share: float = 0.3
    # sd логита склонности принимать приглашения.
    acceptance_logit_sd: float = 1.0
    fsp_history_share: float = 0.3
    # Доля семейств специализации, слитых читеру.
    leak_share: float = 0.3
    relocation_share: float = 0.2
    response: ResponseModel = field(default_factory=ResponseModel)


D1 = GeneratorParams("d1", D1_SEED)
D2 = replace(
    D1,
    name="d2",
    seed=D2_SEED,
    common_modes=((0.5, -1.0, 0.5), (0.5, 1.6, 0.5)),
    topic_sd=1.0,
    speed_sd=0.45,
    salary_scale=1.15,
    salary_sd=0.35,
    response=ResponseModel(
        slip=0.05,
        value_guess=0.05,
        choice_guess_factor=1.5,
        rt_median_seconds=90.0,
        rt_difficulty_slope=0.15,
        rt_noise_sd=0.6,
    ),
)
DATASETS = {p.name: p for p in (D1, D2)}


class Gender(enum.StrEnum):
    male = "male"
    female = "female"


@dataclass(frozen=True)
class Person:
    """Защищённые признаки в резюме: пол — по имени, возраст и вуз."""

    name: str
    gender: Gender
    age: int
    university: str

    @property
    def older(self) -> bool:
        return self.age >= OLDER_FROM

    @property
    def leading(self) -> bool:
        return self.university in LEADING_UNIVERSITIES


def person(rng: random.Random, experience: int) -> Person:
    """Пол, возраст и вуз независимо друг от друга и от истины."""
    gender = Gender.female if rng.random() < 0.5 else Gender.male
    older = rng.random() < 0.5
    leading = rng.random() < 0.5
    return _person(rng, experience, gender, older, leading, rng.randrange(len(SURNAMES)))


def opposite(p: Person, experience: int, rng: random.Random) -> Person:
    """Двойник M5: другой пол, другая группа возраста и вуза; фамилия та же."""
    surname = next(i for i, s in enumerate(SURNAMES) if p.name.endswith((s, s + "а")))
    gender = Gender.male if p.gender == Gender.female else Gender.female
    return _person(rng, experience, gender, not p.older, not p.leading, surname)


def _person(
    rng: random.Random, experience: int, gender: Gender, older: bool, leading: bool, surname: int
) -> Person:
    names = FEMALE_NAMES if gender == Gender.female else MALE_NAMES
    last = SURNAMES[surname] + ("а" if gender == Gender.female else "")
    low, high = AGE_SHIFT[older]
    return Person(
        f"{rng.choice(names)} {last}",
        gender,
        21 + experience + rng.randint(low, high),
        rng.choice(LEADING_UNIVERSITIES if leading else REGIONAL_UNIVERSITIES),
    )


@dataclass(frozen=True)
class ObservedCandidate:
    """Что о кандидате видит платформа: опрос и заявка, самоописание, ответы с временем."""

    id: uuid.UUID
    specialization: str
    claimed: str
    stack: tuple[str, ...]
    about: str
    experience_years: int
    expected_salary: int
    work_formats: tuple[WorkFormat, ...]
    city: str | None
    relocation: bool
    fsp_sub: str | None
    # Семейство банка специализации → ответ на его экземпляр.
    answers: dict[str, Response]
    # Личные данные резюме (M5): оценка и подбор их не видят.
    person: Person


@dataclass(frozen=True)
class Employer:
    id: uuid.UUID
    name: str
    industry: str
    # Истина: вилки компании ниже рынка, по рынку или выше.
    position: SalaryPosition


@dataclass(frozen=True)
class SyntheticNeed:
    """Потребность — то, что работодатель ввёл в форму."""

    id: uuid.UUID
    employer: uuid.UUID
    form: NeedForm


@dataclass(frozen=True)
class Pair:
    need: uuid.UUID
    candidate: uuid.UUID
    share: float
    grade: int


@dataclass(frozen=True)
class Dataset:
    params: GeneratorParams
    # Истинные параметры семейств всех специализаций.
    families: dict[str, Parameters]
    truths: tuple[CandidateTruth, ...]
    observed: tuple[ObservedCandidate, ...]
    employers: tuple[Employer, ...]
    needs: tuple[SyntheticNeed, ...]
    # Реестр ФСП в формате заглушки: ФСП ID → достижения.
    registry: dict[str, list[dict[str, Any]]] = field(default_factory=dict)


def as_candidate(truth: CandidateTruth) -> Candidate:
    """Кандидат стенда с полной истиной: тест на `Market` идёт по модели ответа."""
    return Candidate(truth.level, truth.claimed, truth)


def market_salary(grade: str | None, params: GeneratorParams) -> float:
    """Медиана грейда до НДФЛ; ниже младшего грейда — медиана стажёра."""
    return SALARY_NET_MEDIAN[grade or "intern"] / (1 - NDFL) * params.salary_scale


def snapshot(need: SyntheticNeed, catalog: Catalog, mechanics: Mechanics) -> NeedSnapshot:
    """Снимок потребности по правилам подбора — из тех же доменных типов, что вход работодателя."""
    form = need.form
    terms = need_terms(
        form,
        catalog.specializations.get(form.specialization),
        catalog.grades.get(form.grade),
        [catalog.technologies[c] for c in form.stack],
    )
    return need_snapshot(
        need_content(terms, NOW),
        requirement=mechanics.grade_thresholds[form.grade],
        importance_weights=mechanics.need_importance_weights,
        key_min_technologies=mechanics.need_key_topic_min_technologies,
    )


def label(
    truths: Iterable[CandidateTruth],
    needs: Iterable[SyntheticNeed],
    catalog: Catalog,
    mechanics: Mechanics,
) -> list[Pair]:
    """Эталон пар «потребность — кандидат»: пул потребности — кандидаты её специализации."""
    by_specialization: dict[str, list[CandidateTruth]] = {}
    for truth in truths:
        by_specialization.setdefault(truth.specialization, []).append(truth)
    pairs = []
    for need in needs:
        snap = snapshot(need, catalog, mechanics)
        for truth in by_specialization.get(need.form.specialization, []):
            found = relevance(truth, snap)
            pairs.append(Pair(need.id, truth.id, found.share, found.grade))
    return pairs


class Generator:
    """Генератор набора по `params`. Кандидаты специализации — свой поток случайности истины
    и свой — наблюдаемого: правка самоописания не сдвигает истину."""

    def __init__(self, params: GeneratorParams, mechanics: Mechanics, catalog: Catalog) -> None:
        self.params = params
        self.mechanics = mechanics
        self.catalog = catalog
        self.grades = grades_by_threshold(mechanics.grade_thresholds)
        runner = InProcessCodeRunner()
        self.bank = {
            s: families_for_topics([t.code for t in spec.topics])
            for s, spec in catalog.specializations.items()
        }
        # Угадывание по виду ответа — по первому экземпляру: вид у семейства один.
        self.guess = {
            f.code: guessing(f.instance(0, runner), params.response)
            for families in self.bank.values()
            for f in families
        }

    def rng(self, stream: str) -> random.Random:
        return random.Random(f"{self.params.seed}:{stream}")

    def generate(self) -> Dataset:
        families = self.families()
        employers = self.employers()
        needs = tuple(n for s in self.catalog.specializations for n in self.needs(s, employers))
        truths: list[CandidateTruth] = []
        observed: list[ObservedCandidate] = []
        registry: dict[str, list[dict[str, Any]]] = {}
        for code in self.catalog.specializations:
            truth_rng, seen_rng = self.rng(f"candidates:{code}"), self.rng(f"observed:{code}")
            # Личные данные — свой поток: остальное наблюдаемое от них не сдвигается.
            person_rng = self.rng(f"person:{code}")
            own_needs = [n for n in needs if n.form.specialization == code]
            for persona in self.personas(truth_rng):
                truth = self.truth(code, persona, truth_rng)
                seen, achievements = self.observe(truth, own_needs, families, seen_rng, person_rng)
                truths.append(truth)
                observed.append(seen)
                if truth.fsp_sub is not None:
                    registry[truth.fsp_sub] = achievements
        return Dataset(
            self.params, families, tuple(truths), tuple(observed), employers, needs, registry
        )

    def families(self) -> dict[str, Parameters]:
        """Истинные параметры семейств всех специализаций. Поток — тот же, что у `Market` с этим
        seed: истина семейств набора и стенда одна."""
        found: dict[str, Parameters] = {}
        for bank in self.bank.values():
            found |= true_parameters(
                bank, lambda grade: expert(grade, self.mechanics), random.Random(self.params.seed)
            )
        return found

    def personas(self, rng: random.Random) -> list[Persona]:
        """Персонажи специализации точно по долям плана, в случайном порядке."""
        found = _by_shares(self.params.persona_shares, self.params.candidates_per_specialization)
        rng.shuffle(found)
        return found

    def employers(self) -> tuple[Employer, ...]:
        rng = self.rng("employers")
        positions = _by_shares(self.params.salary_position_shares, self.params.employers)
        rng.shuffle(positions)
        industries = sorted(i.code for i in load_catalog(CATALOG_FILE).industries)
        return tuple(
            Employer(_uuid(rng), f"Компания {i + 1}", rng.choice(industries), position)
            for i, position in enumerate(positions)
        )

    def needs(self, code: str, employers: Sequence[Employer]) -> list[SyntheticNeed]:
        """Потребности специализации, грейды поровну."""
        rng = self.rng(f"needs:{code}")
        found = []
        for i in range(self.params.needs_per_specialization):
            grade = self.grades[i % len(self.grades)]
            employer = rng.choice(employers)
            form = self.need_form(code, grade, employer.name, employer.position, rng)
            found.append(SyntheticNeed(_uuid(rng), employer.id, form))
        return found

    def need_form(
        self, code: str, grade: str, company: str, position: SalaryPosition, rng: random.Random
    ) -> NeedForm:
        """Форма потребности: стек экосистемы, формат и вилка вокруг медианы грейда по позиции
        компании; иногда работодатель сам делает тему ключевой."""
        spec = self.catalog.specializations[code]
        work_format = _weighted(rng, NEED_FORMATS)
        center = (
            market_salary(grade, self.params)
            * dict(self.params.salary_position_factor)[position]
            * math.exp(rng.gauss(0, self.params.need_salary_sd))
        )
        spread = self.params.need_salary_spread
        edited = {}
        if rng.random() < self.params.need_edited_share:
            edited[rng.choice(spec.topics).code] = TopicImportance.key
        return NeedForm(
            title=f"{self.catalog.grades[grade].name} {ROLE[code]}",
            team_description=f"Команда компании «{company}»",
            specialization=code,
            grade=grade,
            stack=self.stack(code, rng, None),
            topic_importance=edited,
            work_format=work_format,
            city=None if work_format == WorkFormat.remote else _weighted(rng, CITIES),
            salary_from=_rounded(center * (1 - spread)),
            salary_to=_rounded(center * (1 + spread)),
        )

    def truth(
        self,
        code: str,
        persona: Persona,
        rng: random.Random,
        *,
        common: float | None = None,
        topic_sd: float | None = None,
        claimed: str | None = None,
    ) -> CandidateTruth:
        """Истина кандидата. `common`, `topic_sd` и `claimed` задаются для демо-набора: кандидат
        нужной категории, а не случайный."""
        p = self.params
        if common is None:
            mean, sd = _weighted(rng, [((m, sd), w) for w, m, sd in p.common_modes])
            common = rng.gauss(mean, sd)
        topics = [t.code for t in self.catalog.specializations[code].topics]
        level = {
            t: common + rng.gauss(0, p.topic_sd if topic_sd is None else topic_sd) for t in topics
        }
        prior = specialization_prior(topics, self.mechanics)
        overall = sum(w * level[t] for t, w in zip(prior.topics, prior.weights, strict=True))
        thresholds = self.mechanics.grade_thresholds
        passed = [g for g in self.grades if overall >= thresholds[g]]
        grade = passed[-1] if passed else None
        if claimed is None:
            true_index = self.grades.index(grade) if grade else 0
            shift = rng.choices([0, 1, -1], weights=p.claimed_shift_weights)[0]
            claimed = self.grades[min(max(true_index + shift, 0), len(self.grades) - 1)]
        formats = _weighted(rng, CANDIDATE_FORMATS)
        city = None if formats == (WorkFormat.remote,) else _weighted(rng, CITIES)
        bank = self.bank[code]
        leaked = (
            frozenset(f.code for f in rng.sample(bank, round(p.leak_share * len(bank))))
            if persona == Persona.bank_leak
            else frozenset()
        )
        return CandidateTruth(
            id=_uuid(rng),
            specialization=code,
            persona=persona,
            common=common,
            level=level,
            grade=grade,
            claimed=claimed,
            expected_salary=_rounded(market_salary(grade, p) * math.exp(rng.gauss(0, p.salary_sd))),
            work_formats=formats,
            city=city,
            relocation=rng.random() < p.relocation_share,
            acceptance=1 / (1 + math.exp(-rng.gauss(0, p.acceptance_logit_sd))),
            speed=rng.gauss(0, p.speed_sd),
            leaked=leaked,
            fsp_sub=str(_uuid(rng)) if rng.random() < p.fsp_history_share else None,
        )

    def observe(
        self,
        truth: CandidateTruth,
        needs: Sequence[SyntheticNeed],
        families: Mapping[str, Parameters],
        rng: random.Random,
        person_rng: random.Random,
    ) -> tuple[ObservedCandidate, list[dict[str, Any]]]:
        """Наблюдаемое из истины: самоописание, ответы на экземпляр каждого семейства и
        достижения ФСП; личные данные — из `person_rng`, от истины не зависят."""
        stack, about = self.self_description(truth, needs, rng)
        low, high = EXPERIENCE_YEARS[truth.grade]
        answers = {
            f.code: respond(
                truth,
                f.code,
                f.topic,
                families[f.code],
                self.guess[f.code],
                self.params.response,
                rng,
            )
            for f in self.bank[truth.specialization]
        }
        achievements = self.achievements(truth, rng) if truth.fsp_sub else []
        experience = rng.randint(low, high)
        seen = ObservedCandidate(
            id=truth.id,
            specialization=truth.specialization,
            claimed=truth.claimed,
            stack=stack,
            about=about,
            experience_years=experience,
            expected_salary=truth.expected_salary,
            work_formats=truth.work_formats,
            city=truth.city,
            relocation=truth.relocation,
            fsp_sub=truth.fsp_sub,
            answers=answers,
            person=person(person_rng, experience),
        )
        return seen, achievements

    def self_description(
        self, truth: CandidateTruth, needs: Sequence[SyntheticNeed], rng: random.Random
    ) -> tuple[tuple[str, ...], str]:
        """Стек и «о себе». Честный пишет стек своей экосистемы и чем сильнее тема технологии,
        тем вероятнее её указывает; накрутчик дописывает стек и названия вакансий своей
        специализации, истинный уровень у него тот же."""
        code = truth.specialization
        stack = list(self.stack(code, rng, truth))
        about = f"{ROLE[code].capitalize()}."
        if truth.persona == Persona.resume_inflator and needs:
            copied = rng.sample(list(needs), min(2, len(needs)))
            for need in copied:
                stack += [t for t in need.form.stack if t not in stack]
            titles = ", ".join(n.form.title for n in copied)
            about += f" Ищу позицию: {titles}."
        names = ", ".join(self.catalog.technologies[t].name for t in stack)
        return tuple(stack), f"{about} Стек: {names}."

    def stack(self, code: str, rng: random.Random, truth: CandidateTruth | None) -> tuple[str, ...]:
        """Ядро экосистемы и дополнения специализации; у кандидата вероятность дополнения растёт
        с его уровнем по темам технологии."""
        core = _weighted(rng, ECOSYSTEMS[code])
        stack = list(core)
        for tech in ADDONS[code]:
            share = (USAGE.get(tech) or USAGE_ESTIMATED[tech]) / 100
            if truth is not None:
                share *= 0.5 + _sigmoid(_tech_level(truth, self.catalog.technologies[tech].topics))
            if rng.random() < min(1.0, share) and tech not in stack:
                stack.append(tech)
        return tuple(stack)

    def achievements(self, truth: CandidateTruth, rng: random.Random) -> list[dict[str, Any]]:
        """Результаты ФСП в формате реестра заглушки: чем выше истинный уровень, тем выше
        результат."""
        found = []
        for _ in range(rng.randint(1, 3)):
            score = truth.common + rng.gauss(0, 0.7)
            result = (
                "winner"
                if score >= 2.2
                else "prize"
                if score >= 1.4
                else "finalist"
                if score >= 0.4
                else "participant"
            )
            discipline = rng.choice(fsp_stub.DISCIPLINES[truth.specialization])
            role = truth.specialization if discipline == "product" and rng.random() < 0.6 else None
            found.append(fsp_stub.achievement(rng, result, discipline, role))
        return sorted(found, key=lambda a: a["date"])


def _tech_level(truth: CandidateTruth, topics: Iterable[str]) -> float:
    own = [truth.level[t] for t in topics if t in truth.level]
    return sum(own) / len(own) if own else truth.common


def _sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def _uuid(rng: random.Random) -> uuid.UUID:
    return uuid.UUID(int=rng.getrandbits(128), version=4)


def _rounded(rub: float) -> int:
    return max(SALARY_ROUNDING, round(rub / SALARY_ROUNDING) * SALARY_ROUNDING)


def _weighted[T](rng: random.Random, options: Sequence[tuple[T, float]]) -> T:
    return rng.choices([o for o, _ in options], weights=[w for _, w in options])[0]


def _by_shares[T](shares: Sequence[tuple[T, float]], total: int) -> list[T]:
    """Ровно `total` значений по долям — наибольшими остатками."""
    exact = [(value, share * total) for value, share in shares]
    counts = {value: math.floor(x) for value, x in exact}
    rest = total - sum(counts.values())
    by_remainder = sorted(exact, key=lambda vx: -(vx[1] - math.floor(vx[1])))
    for value, _ in by_remainder[:rest]:
        counts[value] += 1
    return [value for value, _ in shares for _ in range(counts[value])]


# --- Файлы набора -------------------------------------------------------------------------------

TRUTH_DIR = "truth"
OBSERVED_DIR = "observed"
NEEDS_FILE = "needs.jsonl"
EMPLOYERS_FILE = "employers.jsonl"
PAIRS_FILE = "pairs.jsonl"


def write(dataset: Dataset, directory: Path, catalog: Catalog, mechanics: Mechanics) -> None:
    """Набор в каталог `directory`: истина и наблюдаемое — в разных подкаталогах, эталон пар —
    отдельным файлом."""
    truth_dir, seen_dir = directory / TRUTH_DIR, directory / OBSERVED_DIR
    truth_dir.mkdir(parents=True, exist_ok=True)
    seen_dir.mkdir(parents=True, exist_ok=True)
    _lines(truth_dir / "candidates.jsonl", map(truth_json, dataset.truths))
    _dump(
        truth_dir / "families.json",
        {
            code: {"discrimination": _r(p.discrimination), "difficulty": _r(p.difficulty)}
            for code, p in sorted(dataset.families.items())
        },
    )
    _lines(
        truth_dir / "employers.jsonl",
        ({"id": str(e.id), "position": e.position.value} for e in dataset.employers),
    )
    _lines(seen_dir / "candidates.jsonl", map(observed_json, dataset.observed))
    _dump(seen_dir / "fsp_registry.json", dataset.registry)
    _lines(
        directory / EMPLOYERS_FILE,
        ({"id": str(e.id), "name": e.name, "industry": e.industry} for e in dataset.employers),
    )
    _lines(directory / NEEDS_FILE, map(need_json, dataset.needs))
    pairs = label(dataset.truths, dataset.needs, catalog, mechanics)
    _lines(directory / PAIRS_FILE, map(pair_json, pairs))


def label_files(directory: Path, catalog: Catalog, mechanics: Mechanics) -> list[Pair]:
    """Разметка по файлам набора: читает только истину кандидатов и потребности."""
    truths = [truth_from_json(row) for row in _read(directory / TRUTH_DIR / "candidates.jsonl")]
    needs = [need_from_json(row) for row in _read(directory / NEEDS_FILE)]
    return label(truths, needs, catalog, mechanics)


def truth_json(t: CandidateTruth) -> dict[str, Any]:
    return {
        "id": str(t.id),
        "specialization": t.specialization,
        "persona": t.persona.value,
        # Уровни — без округления: разметка по файлу совпадает с разметкой в памяти и на границе
        # требования.
        "common": t.common,
        "level": t.level,
        "grade": t.grade,
        "claimed": t.claimed,
        "expected_salary": t.expected_salary,
        "work_formats": [f.value for f in t.work_formats],
        "city": t.city,
        "relocation": t.relocation,
        "acceptance": _r(t.acceptance),
        "speed": _r(t.speed),
        "leaked": sorted(t.leaked),
        "fsp_sub": t.fsp_sub,
    }


def truth_from_json(row: Mapping[str, Any]) -> CandidateTruth:
    return CandidateTruth(
        id=uuid.UUID(row["id"]),
        specialization=row["specialization"],
        persona=Persona(row["persona"]),
        common=row["common"],
        level=dict(row["level"]),
        grade=row["grade"],
        claimed=row["claimed"],
        expected_salary=row["expected_salary"],
        work_formats=tuple(WorkFormat(f) for f in row["work_formats"]),
        city=row["city"],
        relocation=row["relocation"],
        acceptance=row["acceptance"],
        speed=row["speed"],
        leaked=frozenset(row["leaked"]),
        fsp_sub=row["fsp_sub"],
    )


def observed_json(o: ObservedCandidate) -> dict[str, Any]:
    return {
        "id": str(o.id),
        "specialization": o.specialization,
        "claimed": o.claimed,
        "stack": list(o.stack),
        "about": o.about,
        "experience_years": o.experience_years,
        "expected_salary": o.expected_salary,
        "work_formats": [f.value for f in o.work_formats],
        "city": o.city,
        "relocation": o.relocation,
        "fsp_sub": o.fsp_sub,
        "name": o.person.name,
        "gender": o.person.gender.value,
        "age": o.person.age,
        "university": o.person.university,
        # Семейство → [верно, секунды].
        "answers": {k: [int(r.correct), round(r.seconds, 1)] for k, r in o.answers.items()},
    }


def need_json(n: SyntheticNeed) -> dict[str, Any]:
    f = n.form
    return {
        "id": str(n.id),
        "employer": str(n.employer),
        "title": f.title,
        "team_description": f.team_description,
        "specialization": f.specialization,
        "grade": f.grade,
        "stack": list(f.stack),
        "topic_importance": {k: v.value for k, v in f.topic_importance.items()},
        "work_format": f.work_format.value,
        "city": f.city,
        "salary_from": f.salary_from,
        "salary_to": f.salary_to,
    }


def need_from_json(row: Mapping[str, Any]) -> SyntheticNeed:
    form = NeedForm(
        title=row["title"],
        team_description=row["team_description"],
        specialization=row["specialization"],
        grade=row["grade"],
        stack=tuple(row["stack"]),
        topic_importance={k: TopicImportance(v) for k, v in row["topic_importance"].items()},
        work_format=WorkFormat(row["work_format"]),
        city=row["city"],
        salary_from=row["salary_from"],
        salary_to=row["salary_to"],
    )
    return SyntheticNeed(uuid.UUID(row["id"]), uuid.UUID(row["employer"]), form)


def pair_json(p: Pair) -> dict[str, Any]:
    return {"need": str(p.need), "candidate": str(p.candidate), "m": _r(p.share), "rel": p.grade}


def _r(x: float) -> float:
    return round(x, 6)


def _text(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def _dump(path: Path, data: object) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, sort_keys=True, indent=1) + "\n", encoding="utf-8"
    )


def _lines(path: Path, rows: Iterable[object]) -> None:
    path.write_text("".join(_text(row) + "\n" for row in rows), encoding="utf-8")


def _read(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)
