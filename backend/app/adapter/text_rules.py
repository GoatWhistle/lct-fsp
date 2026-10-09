"""Разбор потребности и резюме на правилах и словаре синонимов — реализация порта
`TextUnderstanding` (docs/adr/0002-text-understanding-port.md). Вариант по умолчанию и запасной
путь для модели.

Словарь — данные (`config/synonyms.yaml`), названия записей справочника узнаются и без него.
Специализацию, грейд и направление вне справочника решает перевес упоминаний: упоминание в первой
строке — обычно заголовке вакансии — весит `TITLE_WEIGHT`. Правила ничего не выдумывают: чего в
тексте нет, того нет и в черновике. Инструкции в тексте для правил — просто слова.

Уверенность у правил двузначная: `SURE` — значение названо прямо и без соперников, `UNSURE` —
выведено косвенно (специализация по стеку, грейд по стажу), соперники поровну или вилка «на руки».

В резюме правила берут ФИО и контакты по их виду, стек — по справочнику, роли и софт-скиллы — по
словарю: в черновик идёт название записи словаря, а не фраза из текста. Стаж — из прямого «опыт
N лет», иначе из суммы периодов работы в разделе опыта. Софт-скиллы всегда неуверенные.

Записи опыта — по периодам в разделе опыта: текст записи — от её периода до следующего. Место —
первая строка записи без частей, которые называют роль, роль — название словаря в той же строке,
технологии — справочника во всём тексте записи. «Что делал» правила не заполняют. Без заголовка
раздела опыта записей нет: годы учёбы — не опыт. Записи всегда неуверенные.
"""

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from app.domain.catalog import Catalog
from app.domain.experience import ExperienceInput, Month
from app.domain.need_draft import DraftField, NeedDraft, OutOfCatalog
from app.domain.resume_draft import GradeHintRule, ResumeDraft, ResumeField
from app.domain.work import WorkFormat

SURE = 1.0
UNSURE = 0.5
TITLE_WEIGHT = 3
# Первая строка длиннее — не заголовок, а начало описания.
TITLE_MAX = 120
# Где искать «на руки» и валюту вокруг вилки, знаков.
SALARY_CONTEXT = 40

# Резюме: ФИО ищется в первых строках, имя — от двух до трёх слов с заглавной.
NAME_LINES = 5
_NAME_WORD = r"[А-ЯЁA-Z][а-яёa-z]+(?:-[А-ЯЁA-Z][а-яёa-z]+)?"
_NAME_LABEL = re.compile(r"^(?:фио|имя|name)(?![\w-])[\s:—–-]*", re.IGNORECASE)
# Заголовки, которые выглядят как имя, но им не являются.
_NOT_NAME = frozenset(
    {
        "резюме", "curriculum", "vitae", "cv", "контакты", "контактная", "информация", "опыт",
        "работы", "образование", "навыки", "обо", "мне", "себе", "профиль", "summary",
        "experience", "education", "skills", "contacts",
    }
)  # fmt: skip
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_RU_PHONE = re.compile(
    r"(?<![\d+])(?:\+7|8)[\s(-]*(\d{3})[\s)-]*(\d{3})[\s-]*(\d{2})[\s-]*(\d{2})(?!\d)"
)
_PHONE = re.compile(r"(?<![\d+])\+\d{1,3}(?:[\s()-]*\d){8,12}(?!\d)")
_TELEGRAM = re.compile(
    r"(?:t\.me/|telegram\W{0,3}|(?<!\w)tg\W{0,3})@?([A-Za-z][A-Za-z0-9_]{4,31})(?![\w.])",
    re.IGNORECASE,
)
_BARE_TELEGRAM = re.compile(r"(?<![\w.@/])@([A-Za-z][A-Za-z0-9_]{4,31})(?![\w.@])")
_EXPERIENCE = re.compile(
    # «Стаж» — без «стажировки» и «стажёра»: срок стажировки — не весь стаж.
    r"(?:опыт\w*|стаж(?:а|ем|у)?)(?!\w)(?: работы)?[^.\n\d]{0,30}?"
    r"(?P<years>\d{1,2}) ?\+? ?(?:лет|года|год)(?!\w)"
    r"|(?P<en>\d{1,2})\+? years? of (?:\w+ )?experience"
)
# Раздел опыта: периоды работы считаются от его заголовка до заголовка следующего раздела.
_EXPERIENCE_SECTION = re.compile(
    r"^(?:опыт работы|профессиональный опыт|места работы|опыт|work experience|experience)\b",
    re.MULTILINE,
)
_NEXT_SECTION = re.compile(
    r"^(?:образование|education|курсы|навыки|ключевые навыки|skills|о себе|обо мне|проекты|"
    r"сертификаты|языки|достижения|хобби)\b",
    re.MULTILINE,
)
_MONTHS = {
    r"январ\w*|jan\w*": 1,
    r"феврал\w*|feb\w*": 2,
    r"март\w*|mar\w*": 3,
    r"апрел\w*|apr\w*": 4,
    r"ма[йя]|may": 5,
    r"июн\w*|jun\w*": 6,
    r"июл\w*|jul\w*": 7,
    r"август\w*|aug\w*": 8,
    r"сентябр\w*|sep\w*": 9,
    r"октябр\w*|oct\w*": 10,
    r"ноябр\w*|nov\w*": 11,
    r"декабр\w*|dec\w*": 12,
}
_MONTH_NAMES = re.compile("|".join(rf"(?:{m})" for m in _MONTHS))


def _point(n: int) -> str:
    return (
        rf"(?:(?P<m{n}>0?[1-9]|1[0-2])[./]|(?P<name{n}>{_MONTH_NAMES.pattern})\.?\s)?"
        rf"(?P<y{n}>(?:19|20)\d{{2}})(?!\d)"
    )


_PRESENT = (
    r"(?:по\s)?(?:н\. ?в\.?|настоящ\w* врем\w*|наст\. вр\.|сейчас|текущ\w* момент\w*"
    r"|present|now|current)"
)
_PERIOD = re.compile(
    rf"(?<!\d){_point(1)}\s?(?:-|–|—|по|to)?\s?(?:(?P<present>{_PRESENT})|{_point(2)})"
)
# Что отделяет период от заголовка записи: «03.2021 — н.в.: QA-инженер».
_ENTRY_LEAD = re.compile(r"[\s:;,.—–-]+")
# Заголовок записи кончается с первой фразой: дальше в той же строке — описание.
_SENTENCE_END = re.compile(r"\.\s")

_WORD = r"[\w+#]"
_NUMBER = r"\d{1,3}(?: \d{3})+|\d+(?:[.,]\d+)?"


class _Foreign(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    synonyms: list[str]
    nearest: list[str]


class _Salary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    min_rub: int
    multipliers: dict[int, list[str]]
    net: list[str]
    foreign: list[str]


class Synonyms(BaseModel):
    """Форма `config/synonyms.yaml`: лишние и пропущенные поля — ошибка."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    specializations: dict[str, list[str]]
    grades: dict[str, list[str]]
    experience_years: dict[str, int]
    technologies: dict[str, list[str]]
    roles: dict[str, list[str]]
    soft_skills: dict[str, list[str]]
    work_formats: dict[WorkFormat, list[str]]
    cities: dict[str, list[str]]
    salary: _Salary
    out_of_catalog: list[_Foreign]


def load_synonyms(path: Path) -> Synonyms:
    with path.open(encoding="utf-8") as f:
        return Synonyms.model_validate(yaml.safe_load(f))


def grade_hint_rule(synonyms: Synonyms) -> GradeHintRule:
    """Подсказка грейда — на тех же порогах стажа и словах грейдов, что разбор потребности:
    правила потребности и резюме не расходятся."""
    return GradeHintRule(
        experience_years=dict(synonyms.experience_years),
        role_words={grade: tuple(words) for grade, words in synonyms.grades.items()},
    )


def normalize(text: str) -> str:
    """Нижний регистр, «ё» как «е», пробелы любого вида — одним пробелом; пустые строки убраны:
    первая строка — первая непустая."""
    text = text.lower().replace("ё", "е")
    lines = (re.sub(r"[^\S\n]+", " ", line).strip() for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def _pattern(synonym: str) -> str:
    """Синоним — целое слово или фраза; звёздочка в конце — основа слова."""
    stem = synonym.endswith("*")
    body = re.escape(normalize(synonym.rstrip("*")))
    return rf"(?<!{_WORD}){body}" + ("" if stem else rf"(?!{_WORD})")


def _unit_pattern(unit: str) -> str:
    """Множитель суммы идёт сразу за числом («300к»), поэтому начало слова не проверяется."""
    stem = unit.endswith("*")
    body = re.escape(normalize(unit.rstrip("*")))
    return body + (r"\w*" if stem else r"(?!\w)") + r"\.?"


def _matcher(synonyms: Iterable[str]) -> re.Pattern[str] | None:
    patterns = sorted({_pattern(s) for s in synonyms if s.strip("* ")}, key=len, reverse=True)
    return re.compile("|".join(patterns)) if patterns else None


@dataclass(frozen=True)
class _Hits:
    """Упоминания значений в тексте: значение → начала совпадений."""

    starts: Mapping[str, tuple[int, ...]]

    def score(self, value: str, title_end: int) -> int:
        return sum(TITLE_WEIGHT if s < title_end else 1 for s in self.starts.get(value, ()))

    def best(self, title_end: int) -> tuple[str | None, int, bool]:
        """Значение с наибольшим весом, вес и есть ли у него соперник с тем же весом. Из равных —
        названное раньше."""
        if not self.starts:
            return None, 0, False
        scores = {v: self.score(v, title_end) for v in self.starts}
        top = max(scores.values())
        leaders = sorted(
            (v for v, s in scores.items() if s == top), key=lambda v: self.starts[v][0]
        )
        return leaders[0], top, len(leaders) > 1


def _find(matchers: Mapping[str, re.Pattern[str]], text: str) -> _Hits:
    starts = {
        value: tuple(m.start() for m in matcher.finditer(text))
        for value, matcher in matchers.items()
    }
    return _Hits({v: s for v, s in starts.items() if s})


@dataclass(frozen=True)
class _Vocabulary:
    """Словарь, собранный под справочник: значение → регулярное выражение его синонимов."""

    specializations: Mapping[str, re.Pattern[str]]
    grades: Mapping[str, re.Pattern[str]]
    technologies: Mapping[str, re.Pattern[str]]
    work_formats: Mapping[str, re.Pattern[str]]
    cities: Mapping[str, re.Pattern[str]]
    foreign: Mapping[str, re.Pattern[str]]
    # Технология → специализации её тем: специализация по стеку, когда её не назвали.
    technology_specializations: Mapping[str, frozenset[str]]


def _matchers(entries: Mapping[str, Iterable[str]]) -> dict[str, re.Pattern[str]]:
    return {value: m for value, synonyms in entries.items() if (m := _matcher(synonyms))}


def _vocabulary(synonyms: Synonyms, catalog: Catalog) -> _Vocabulary:
    def with_names(
        known: Iterable[tuple[str, str]], extra: Mapping[str, list[str]]
    ) -> dict[str, list[str]]:
        # Синонимы кодов, которых нет в справочнике, не нужны: такое значение сценарий отбросит.
        return {code: [name, code, *extra.get(code, [])] for code, name in known}

    specialization_of_topic = {t.code: t.specialization_code for t in catalog.topics()}
    return _Vocabulary(
        specializations=_matchers(
            with_names(
                ((s.code, s.name) for s in catalog.specializations), synonyms.specializations
            )
        ),
        grades=_matchers(with_names(((g.code, g.name) for g in catalog.grades), synonyms.grades)),
        technologies=_matchers(
            with_names(((t.code, t.name) for t in catalog.technologies), synonyms.technologies)
        ),
        work_formats=_matchers({str(f): s for f, s in synonyms.work_formats.items()}),
        cities=_matchers(synonyms.cities),
        foreign=_matchers({f.name: f.synonyms for f in synonyms.out_of_catalog}),
        technology_specializations={
            t.code: frozenset(specialization_of_topic[topic] for topic in t.topics)
            for t in catalog.technologies
        },
    )


@dataclass(frozen=True)
class _FoundSalary:
    low: int | None
    high: int | None
    net: bool


class RulesTextUnderstanding:
    """Реализация порта `TextUnderstanding` на правилах; сети не касается."""

    def __init__(self, synonyms: Synonyms) -> None:
        self._synonyms = synonyms
        self._nearest = {f.name: tuple(f.nearest) for f in synonyms.out_of_catalog}
        # Название записи узнаётся и без синонимов, как у справочника.
        self._roles = _matchers({label: [label, *s] for label, s in synonyms.roles.items()})
        self._soft_skills = _matchers(
            {label: [label, *s] for label, s in synonyms.soft_skills.items()}
        )
        self._vocabularies: dict[Catalog, _Vocabulary] = {}
        salary = synonyms.salary
        units = {
            _unit_pattern(unit): multiplier
            for multiplier, names in salary.multipliers.items()
            for unit in names
        }
        self._units = [
            (re.compile(p), m) for p, m in sorted(units.items(), key=lambda u: -len(u[0]))
        ]
        unit = "|".join(p for p, _ in sorted(units.items(), key=lambda u: -len(u[0])))

        def amount(number: str, multiplier: str) -> str:
            return rf"(?P<{number}>{_NUMBER})(?: ?(?P<{multiplier}>{unit}))?"

        a, b = amount("a", "ua"), amount("b", "ub")
        self._range = re.compile(rf"(?:(?<!\w)от )?{a} ?(?:-|–|—|(?<!\w)до(?!\w)) ?{b}")
        self._from = re.compile(rf"(?<!\w)от ?{a}")
        self._to = re.compile(rf"(?<!\w)до ?{b}")
        self._net = _matcher(salary.net)
        # Знаки валют стоят вплотную к числу — их ищем подстрокой, слова — по границе слова.
        self._currency_signs = tuple(c for c in salary.foreign if not any(ch.isalnum() for ch in c))
        self._currency_words = _matcher(c for c in salary.foreign if c not in self._currency_signs)
        self._experience = re.compile(
            r"опыт\w*[^.\n]{0,40}?(?:(?<!\w)от )?(?P<years>\d{1,2})\+?"
            r"(?: ?(?:-|–|—|до) ?\d{1,2})? ?(?:лет|года|год)(?!\w)"
        )

    def need(self, text: str, catalog: Catalog) -> NeedDraft | OutOfCatalog:
        vocabulary = self._vocabulary(catalog)
        raw_title = next((line.strip() for line in text.splitlines() if line.strip()), "")
        text = normalize(text)
        title_end = text.find("\n") if "\n" in text else len(text)
        confidence: dict[DraftField, float | None] = {}

        specializations = _find(vocabulary.specializations, text)
        specialization, spec_score, spec_tied = specializations.best(title_end)
        foreign, foreign_score, _ = _find(vocabulary.foreign, text).best(title_end)
        if foreign is not None and foreign_score > spec_score:
            return OutOfCatalog(asked=foreign, nearest=self._nearest[foreign])

        stack = tuple(sorted(_find(vocabulary.technologies, text).starts))
        if stack:
            confidence[DraftField.stack] = SURE
        if specialization is not None:
            confidence[DraftField.specialization] = UNSURE if spec_tied else SURE
        else:
            specialization = self._by_stack(stack, vocabulary)
            if specialization is not None:
                confidence[DraftField.specialization] = UNSURE

        grade, _, grade_tied = _find(vocabulary.grades, text).best(title_end)
        if grade is not None:
            confidence[DraftField.grade] = UNSURE if grade_tied else SURE
        else:
            grade = self._by_experience(text)
            if grade is not None:
                confidence[DraftField.grade] = UNSURE

        work_format = self._work_format(_find(vocabulary.work_formats, text), confidence)
        cities = _find(vocabulary.cities, text)
        city, _, _ = cities.best(0)
        if city is not None:
            confidence[DraftField.city] = SURE if len(cities.starts) == 1 else UNSURE

        salary = self._salary(text)
        if salary.low is not None or salary.high is not None:
            confidence[DraftField.salary] = UNSURE if salary.net else SURE

        return NeedDraft(
            title=raw_title if 0 < len(raw_title) <= TITLE_MAX else None,
            specialization=specialization,
            grade=grade,
            stack=stack,
            work_format=work_format,
            city=city,
            salary_from=salary.low,
            salary_to=salary.high,
            confidence=confidence,
        )

    def resume(self, text: str, catalog: Catalog, today: date) -> ResumeDraft:
        vocabulary = self._vocabulary(catalog)
        normalized = normalize(text)
        confidence: dict[ResumeField, float | None] = {}

        full_name, name_sure = self._full_name(text, vocabulary)
        if full_name is not None:
            confidence[ResumeField.full_name] = SURE if name_sure else UNSURE
        email = _EMAIL.search(text)
        if email:
            confidence[ResumeField.contact_email] = SURE
        phone = _phone(text)
        if phone is not None:
            confidence[ResumeField.contact_phone] = SURE
        telegram = _TELEGRAM.search(text)
        if telegram:
            confidence[ResumeField.telegram] = SURE
        elif telegram := _BARE_TELEGRAM.search(text):
            confidence[ResumeField.telegram] = UNSURE

        stack = tuple(sorted(_find(vocabulary.technologies, normalized).starts))
        roles = self._labels(self._roles, normalized)
        soft_skills = self._labels(self._soft_skills, normalized)
        for name, found in (
            (ResumeField.stack, stack),
            (ResumeField.job_roles, roles),
        ):
            if found:
                confidence[name] = SURE
        # Софт-скиллы — слова из описаний работы, а не названия: их стоит проверить.
        if soft_skills:
            confidence[ResumeField.soft_skills] = UNSURE

        experience = _stated_experience(normalized)
        if experience is not None:
            confidence[ResumeField.experience_years] = SURE
        else:
            experience = _experience_by_periods(normalized, today)
            if experience is not None:
                confidence[ResumeField.experience_years] = UNSURE
        entries = self._entries(text, vocabulary, today)
        if entries:
            confidence[ResumeField.experience] = UNSURE

        return ResumeDraft(
            full_name=full_name,
            contact_email=email[0] if email else None,
            contact_phone=phone,
            telegram=telegram[1] if telegram else None,
            stack=stack,
            job_roles=roles,
            experience_years=experience,
            soft_skills=soft_skills,
            confidence=confidence,
            experience=entries,
        )

    def _entries(
        self, text: str, vocabulary: _Vocabulary, today: date
    ) -> tuple[ExperienceInput, ...]:
        """Записи опыта по периодам раздела опыта. Ищется по нормализованному тексту, место
        берётся из текста с исходным регистром — они совпадают по позициям знаков. Конец после
        сегодня записи не мешает — годы по технологиям его не досчитают."""
        cased = "\n".join(" ".join(line.split()) for line in text.splitlines() if line.strip())
        lowered = cased.lower().replace("ё", "е")
        if len(lowered) != len(cased):
            cased = lowered
        bounds = _experience_section(lowered)
        if bounds is None:
            return ()
        # Запись кончается на следующем периоде — любом, даже на том, который записью не станет:
        # его текст не уходит в соседнюю запись.
        periods = list(_PERIOD.finditer(lowered, bounds[0], bounds[1]))
        now = Month.of(today)
        entries = []
        for i, found in enumerate(periods):
            start, end = _entry_period(found)
            if start > now or (end is not None and end < start):
                continue
            stop = periods[i + 1].start() if i + 1 < len(periods) else bounds[1]
            lead = _ENTRY_LEAD.match(lowered, found.end(), stop)
            body = lead.end() if lead else found.end()
            block = lowered[body:stop]
            title_end = body + len(_SENTENCE_END.split(block.split("\n", 1)[0], 1)[0])
            title, title_cased = lowered[body:title_end], cased[body:title_end]
            roles = self._labels(self._roles, title)
            entries.append(
                ExperienceInput(
                    place=self._place(title, title_cased),
                    role=roles[0] if roles else "",
                    start=start,
                    end=end,
                    stack=tuple(sorted(_find(vocabulary.technologies, block).starts)),
                    summary="",
                )
            )
        return tuple(entries)

    def _place(self, title: str, title_cased: str) -> str:
        """Заголовок записи без частей через запятую, которые называют роль: «Тимлид бэкенда,
        ООО «Сервисы»» → «ООО «Сервисы»». Весь заголовок — роль: место — он сам."""
        parts = [
            cased.strip()
            for part, cased in zip(title.split(","), title_cased.split(","), strict=True)
            if not any(m.search(part) for m in self._roles.values())
        ]
        place = ", ".join(p for p in parts if p) or title_cased.strip()
        return place.rstrip(".,;: ")

    @staticmethod
    def _labels(matchers: Mapping[str, re.Pattern[str]], text: str) -> tuple[str, ...]:
        """Названия записей словаря в порядке первого упоминания."""
        starts = _find(matchers, text).starts
        return tuple(sorted(starts, key=lambda label: starts[label][0]))

    def _full_name(self, text: str, vocabulary: _Vocabulary) -> tuple[str | None, bool]:
        """ФИО — первые два-три слова с заглавной в одной из первых строк, если ни одно из них
        не заголовок, не технология, не роль и не город. Уверенно — когда в строке только
        полное ФИО из трёх слов."""
        lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
        known = [
            *vocabulary.technologies.values(),
            *vocabulary.specializations.values(),
            *vocabulary.grades.values(),
            *vocabulary.cities.values(),
            *self._roles.values(),
        ]
        for line in lines[:NAME_LINES]:
            line = _NAME_LABEL.sub("", line)
            for count in (3, 2):
                found = re.match(rf"{_NAME_WORD}(?: {_NAME_WORD}){{{count - 1}}}(?![\w-])", line)
                if found is None:
                    continue
                name = found[0]
                words = normalize(name).split()
                if any(w in _NOT_NAME for w in words) or any(
                    m.search(normalize(name)) for m in known
                ):
                    continue
                return name, count == 3 and name == line
        return None, False

    def _vocabulary(self, catalog: Catalog) -> _Vocabulary:
        # Хранится словарь только последней версии справочника: после синхронизации старый не нужен.
        if catalog not in self._vocabularies:
            self._vocabularies = {catalog: _vocabulary(self._synonyms, catalog)}
        return self._vocabularies[catalog]

    @staticmethod
    def _by_stack(stack: Iterable[str], vocabulary: _Vocabulary) -> str | None:
        """Специализация, к темам которой ведёт больше всего технологий стека; поровну — нет."""
        votes: dict[str, int] = defaultdict(int)
        for tech in stack:
            for specialization in vocabulary.technology_specializations.get(tech, ()):
                votes[specialization] += 1
        if not votes:
            return None
        top = max(votes.values())
        leaders = [s for s, v in votes.items() if v == top]
        return leaders[0] if len(leaders) == 1 else None

    def _by_experience(self, text: str) -> str | None:
        """Грейд по стажу «опыт от N лет»: старший грейд, чей порог стажа не выше N."""
        found = self._experience.search(text)
        if found is None:
            return None
        years = int(found["years"])
        reached = [(y, g) for g, y in self._synonyms.experience_years.items() if y <= years]
        return max(reached)[1] if reached else None

    @staticmethod
    def _work_format(hits: _Hits, confidence: dict[DraftField, float | None]) -> WorkFormat | None:
        """Один формат — он; офис вместе с удалёнкой или гибрид с чем-то ещё — гибрид, но
        неуверенно."""
        found = set(hits.starts)
        if not found:
            return None
        if len(found) == 1:
            confidence[DraftField.work_format] = SURE
            return WorkFormat(found.pop())
        confidence[DraftField.work_format] = UNSURE
        return WorkFormat.hybrid

    def _salary(self, text: str) -> _FoundSalary:
        """Первая вилка в рублях: «от … до …», «200–300к», затем отдельные «от …» и «до …»."""
        for match in self._range.finditer(text):
            low = self._amount(match["a"], match["ua"] or match["ub"])
            high = self._amount(match["b"], match["ub"] or match["ua"])
            if (
                low is not None
                and high is not None
                and low <= high
                and not self._foreign(text, match)
            ):
                return _FoundSalary(low, high, self._is_net(text, match))
        low = high = None
        net = False
        for pattern, group, unit in ((self._from, "a", "ua"), (self._to, "b", "ub")):
            for match in pattern.finditer(text):
                value = self._amount(match[group], match[unit])
                if value is not None and not self._foreign(text, match):
                    if group == "a":
                        low = value
                    else:
                        high = value
                    net = net or self._is_net(text, match)
                    break
        if low is not None and high is not None and low > high:
            return _FoundSalary(None, None, False)
        return _FoundSalary(low, high, net)

    def _amount(self, number: str, unit: str | None) -> int | None:
        value = float(number.replace(" ", "").replace(",", "."))
        if unit:
            value *= next(m for p, m in self._units if p.fullmatch(unit))
        rub = round(value)
        return rub if rub >= self._synonyms.salary.min_rub else None

    def _around(self, text: str, match: re.Match[str]) -> str:
        return text[max(0, match.start() - SALARY_CONTEXT // 2) : match.end() + SALARY_CONTEXT]

    def _foreign(self, text: str, match: re.Match[str]) -> bool:
        around = self._around(text, match)
        if any(sign in around for sign in self._currency_signs):
            return True
        return self._currency_words is not None and self._currency_words.search(around) is not None

    def _is_net(self, text: str, match: re.Match[str]) -> bool:
        return self._net is not None and self._net.search(self._around(text, match)) is not None


def _phone(text: str) -> str | None:
    """Российский номер — в виде «+7 999 123-45-67», другой с кодом страны — как написан."""
    found = _RU_PHONE.search(text)
    if found:
        return f"+7 {found[1]} {found[2]}-{found[3]}-{found[4]}"
    found = _PHONE.search(text)
    return " ".join(found[0].split()) if found else None


def _stated_experience(text: str) -> int | None:
    """Стаж, названный прямо: «опыт работы — 6 лет», «стаж 3 года», «5 years of experience»."""
    found = _EXPERIENCE.search(text)
    if found is None:
        return None
    return int(found["years"] or found["en"])


def _month(number: str | None, name: str | None) -> int | None:
    if number:
        return int(number)
    if name:
        return next(m for pattern, m in _MONTHS.items() if re.fullmatch(pattern, name))
    return None


def _experience_section(text: str) -> tuple[int, int] | None:
    """Где раздел опыта: от конца его заголовка до заголовка следующего раздела."""
    start = _EXPERIENCE_SECTION.search(text)
    if start is None:
        return None
    end = _NEXT_SECTION.search(text, start.end())
    return start.end(), end.start() if end else len(text)


def _periods(text: str, today: date, start: int = 0) -> Iterable[tuple[int, int]]:
    """Периоды работы «03.2019 — н.в.», «2017–2020», «январь 2021 — май 2023» с `start` —
    номерами месяцев: первый включительно, последний — исключительно. Период без месяцев идёт от
    января до января: «2019–2023» — четыре года, «2023 — 2023» — год. Период, который ещё не
    начался или кончается в будущем, пропускается."""
    now = today.year * 12 + today.month
    for found in _PERIOD.finditer(text, start):
        first = int(found["y1"]) * 12 + (_month(found["m1"], found["name1"]) or 1) - 1
        if found["present"]:
            last = now
        else:
            month = _month(found["m2"], found["name2"])
            last = int(found["y2"]) * 12 + (month or 1) - 1 + (1 if month else 0)
            if month is None and last <= first:
                last = first + 12
        if first < last <= now:
            yield first, last


def _entry_period(found: re.Match[str]) -> tuple[Month, Month | None]:
    """Период записи опыта так, как его написали: год без месяцев — с января по декабрь,
    «2019 — 2023» — по декабрь 2023, «по сейчас» — `None`."""
    start = Month(int(found["y1"]), _month(found["m1"], found["name1"]) or 1)
    if found["present"]:
        return start, None
    year = int(found["y2"])
    month = _month(found["m2"], found["name2"])
    return start, Month(year, month) if month else Month(max(year, start.year), 12)


def _experience_by_periods(text: str, today: date) -> int | None:
    """Полных лет в объединении периодов работы (`_periods`). Есть раздел опыта — только периоды
    в нём: годы учёбы стажем не считаются."""
    bounds = _experience_section(text)
    if bounds is not None:
        text = text[: bounds[1]]
    spans = sorted(_periods(text, today, bounds[0] if bounds else 0))
    if not spans:
        return None
    months = 0
    reached = 0
    for first, last in spans:
        first = max(first, reached)
        if last > first:
            months += last - first
            reached = last
    return months // 12
