"""Черновик потребности из свободного текста (mechanics.md, §12; docs/adr/0002).

Порт `TextUnderstanding` превращает текст работодателя в черновик со значениями справочника либо
в ответ «вне справочника» с ближайшими специализациями. Адаптеру сценарий не доверяет: всё, чего
нет в справочнике, отбрасывает `checked`. Черновик — не потребность: важность тем выводит домен из
стека, как для формы, а сохраняется он обычной потребностью после правки человеком.
"""

import enum
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass

from app.domain.catalog import Catalog, CatalogRef
from app.domain.work import WorkFormat

# Длина полей черновика — как у формы потребности.
TITLE_MAX = 200
CITY_MAX = 100
ASKED_MAX = 100


class DraftField(enum.StrEnum):
    """Поля черновика с уверенностью. «Кого ищете» не из справочника — уверенности у него нет."""

    specialization = "specialization"
    grade = "grade"
    stack = "stack"
    work_format = "work_format"
    city = "city"
    salary = "salary"


@dataclass(frozen=True)
class NeedDraft:
    """Что адаптер узнал в тексте — справочники кодами. Чего в тексте нет, то `None` или пусто;
    вилка — рубли в месяц до вычета НДФЛ, одна граница может быть без другой («до 350 000»)."""

    title: str | None
    specialization: str | None
    grade: str | None
    stack: tuple[str, ...]
    work_format: WorkFormat | None
    city: str | None
    salary_from: int | None
    salary_to: int | None
    # Уверенность по полю в [0, 1]; `None` или нет ключа — адаптер её не считает.
    confidence: Mapping[DraftField, float | None]


@dataclass(frozen=True)
class OutOfCatalog:
    """Текст про специализацию, которой нет в справочнике: что просили и ближайшие специализации
    справочника — кодами."""

    asked: str
    nearest: tuple[str, ...]


@dataclass(frozen=True)
class CheckedDraft:
    """Черновик после проверки по справочнику — то, что видит экран «система поняла так»."""

    title: str | None
    specialization: CatalogRef | None
    grade: CatalogRef | None
    # В порядке справочника.
    stack: tuple[CatalogRef, ...]
    work_format: WorkFormat | None
    city: str | None
    salary_from: int | None
    salary_to: int | None
    confidence: Mapping[DraftField, float | None]
    # Распознанные поля с уверенностью ниже порога — экран их подсвечивает.
    uncertain: frozenset[DraftField]


@dataclass(frozen=True)
class CheckedOutOfCatalog:
    asked: str
    # Не пусто: без подсказки от адаптера — все специализации справочника.
    nearest: tuple[CatalogRef, ...]


def cleaned(text: str) -> str:
    """Текст, который видит адаптер: без управляющих и невидимых знаков (нулевой ширины,
    направления письма) — ими прячут слова от человека, который читает тот же текст."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return "".join(
        ch
        for ch in text
        if ch in "\n\t" or unicodedata.category(ch) not in {"Cc", "Cf", "Co", "Cs"}
    )


def _clip(value: object, limit: int) -> str | None:
    """Строка без лишних пробелов не длиннее `limit`; не строка — как если бы поля не было."""
    if not isinstance(value, str):
        return None
    value = " ".join(value.split())[:limit]
    return value or None


def _code(value: object) -> str:
    return value if isinstance(value, str) else ""


def _salary(low: int | None, high: int | None) -> tuple[int | None, int | None]:
    """Граница не больше нуля или не целым числом отбрасывается; перепутанные «от» и «до» —
    обе."""
    low = low if type(low) is int and low > 0 else None
    high = high if type(high) is int and high > 0 else None
    if low is not None and high is not None and low > high:
        return None, None
    return low, high


def checked(draft: NeedDraft, catalog: Catalog, *, confident: float) -> CheckedDraft:
    """Черновик в пределах справочника: неизвестные коды, формат вне перечня, вилка без смысла и
    уверенность вне [0, 1] отбрасываются; значение не того типа — тоже, а не падение. Поле с
    уверенностью ниже `confident` — неуверенное, как и вилка с одной границей: форма её не примет,
    пока работодатель не укажет вторую или не очистит обе."""
    specializations = {s.code: CatalogRef(s.code, s.name) for s in catalog.specializations}
    grades = {g.code: CatalogRef(g.code, g.name) for g in catalog.grades}
    asked_stack = (
        {c for c in draft.stack if isinstance(c, str)}
        if isinstance(draft.stack, list | tuple)
        else set()
    )
    title = _clip(draft.title, TITLE_MAX)
    specialization = specializations.get(_code(draft.specialization))
    grade = grades.get(_code(draft.grade))
    stack = tuple(CatalogRef(t.code, t.name) for t in catalog.technologies if t.code in asked_stack)
    formats = {str(f) for f in WorkFormat}
    work_format = (
        WorkFormat(_code(draft.work_format)) if _code(draft.work_format) in formats else None
    )
    city = _clip(draft.city, CITY_MAX)
    salary_from, salary_to = _salary(draft.salary_from, draft.salary_to)
    recognized = {
        DraftField.specialization: specialization is not None,
        DraftField.grade: grade is not None,
        DraftField.stack: bool(stack),
        DraftField.work_format: work_format is not None,
        DraftField.city: city is not None,
        DraftField.salary: salary_from is not None or salary_to is not None,
    }
    given = draft.confidence if isinstance(draft.confidence, Mapping) else {}
    confidence = {name: _confidence(given.get(name)) for name, found in recognized.items() if found}
    one_bound = (salary_from is None) != (salary_to is None)
    return CheckedDraft(
        title=title,
        specialization=specialization,
        grade=grade,
        stack=stack,
        work_format=work_format,
        city=city,
        salary_from=salary_from,
        salary_to=salary_to,
        confidence=confidence,
        uncertain=frozenset(
            name for name, level in confidence.items() if level is not None and level < confident
        )
        | ({DraftField.salary} if one_bound else set()),
    )


def _confidence(given: object) -> float | None:
    """Уверенность вне [0, 1] или не числом — как если бы адаптер её не считал."""
    if isinstance(given, int | float) and not isinstance(given, bool) and 0 <= given <= 1:
        return float(given)
    return None


def checked_out_of_catalog(answer: OutOfCatalog, catalog: Catalog) -> CheckedOutOfCatalog:
    """Ближайшие — только специализации справочника, без повторов; пустой список подсказок
    заменяется всеми специализациями, чтобы экран не остался без выхода."""
    known = {s.code: CatalogRef(s.code, s.name) for s in catalog.specializations}
    codes = answer.nearest if isinstance(answer.nearest, list | tuple) else ()
    nearest = tuple(known[c] for c in dict.fromkeys(map(_code, codes)) if c in known)
    return CheckedOutOfCatalog(
        asked=_clip(answer.asked, ASKED_MAX) or "",
        nearest=nearest or tuple(known.values()),
    )
