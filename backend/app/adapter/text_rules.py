"""Разбор потребности на правилах и словаре синонимов — реализация порта `TextUnderstanding`
(docs/adr/0002-text-understanding-port.md). Вариант по умолчанию и запасной путь для модели.

Словарь — данные (`config/synonyms.yaml`), названия записей справочника узнаются и без него.
Специализацию, грейд и направление вне справочника решает перевес упоминаний: упоминание в первой
строке — обычно заголовке вакансии — весит `TITLE_WEIGHT`. Правила ничего не выдумывают: чего в
тексте нет, того нет и в черновике. Инструкции в тексте для правил — просто слова.

Уверенность у правил двузначная: `SURE` — значение названо прямо и без соперников, `UNSURE` —
выведено косвенно (специализация по стеку, грейд по стажу), соперники поровну или вилка «на руки».
"""

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from app.domain.catalog import Catalog
from app.domain.need_draft import DraftField, NeedDraft, OutOfCatalog
from app.domain.work import WorkFormat

SURE = 1.0
UNSURE = 0.5
TITLE_WEIGHT = 3
# Первая строка длиннее — не заголовок, а начало описания.
TITLE_MAX = 120
# Где искать «на руки» и валюту вокруг вилки, знаков.
SALARY_CONTEXT = 40

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
    work_formats: dict[WorkFormat, list[str]]
    cities: dict[str, list[str]]
    salary: _Salary
    out_of_catalog: list[_Foreign]


def load_synonyms(path: Path) -> Synonyms:
    with path.open(encoding="utf-8") as f:
        return Synonyms.model_validate(yaml.safe_load(f))


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
