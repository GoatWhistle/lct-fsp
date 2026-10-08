"""Справочники: грейд, сфера бизнеса, специализация, тема, технология, дисциплина ФСП и их
синхронизация.

Ключ каждой записи — стабильный `code`: на него ссылаются тест, профиль и подбор. Содержимое
справочников — `config/catalog.yaml`, в хранилище его кладёт синхронизация по кодам: записи из
файла добавляются или обновляются, коды, которых в файле нет, снимаются. Запись, на которую уже
ссылаются данные, хранилище снять не даст, и это правильно: переименование кода требует миграции
данных.
"""

import enum
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogRef:
    """Ссылка на запись справочника с названием для показа."""

    code: str
    name: str


@dataclass(frozen=True)
class Grade:
    """Грейд — вторая половина категории; `rank` растёт от младшего к старшему."""

    code: str
    name: str
    rank: int


@dataclass(frozen=True)
class Topic:
    """Тема специализации — единица профиля навыков. Код темы начинается с кода
    специализации и точки."""

    code: str
    name: str
    specialization_code: str


@dataclass(frozen=True)
class Technology:
    """Технология стека; `topics` — коды тем, с которыми она связана, любых специализаций."""

    code: str
    name: str
    topics: tuple[str, ...] = ()


@dataclass(frozen=True)
class Specialization:
    """Специализация — IT-направление, «отрасль» в ТЗ; темы — в порядке справочника."""

    code: str
    name: str
    topics: tuple[Topic, ...] = ()


@dataclass(frozen=True)
class Industry:
    """Сфера бизнеса: деятельность компании и интересные кандидату сферы. «Отрасль» из ТЗ —
    другое: IT-направление, то есть специализация."""

    code: str
    name: str


@dataclass(frozen=True)
class FspDiscipline:
    """Дисциплина ФСП: `topics` — коды тем любых специализаций, о которых говорит результат в
    ней (mechanics.md, §11). Дисциплина без тем — результат в ней только факт в профиле."""

    code: str
    name: str
    topics: tuple[str, ...] = ()


@dataclass(frozen=True)
class Catalog:
    """Справочники целиком; порядок в каждом списке — порядок показа. Ссылки согласованы: коды
    уникальны, код темы начинается с кода специализации и точки, технологии и дисциплины ФСП
    указывают на известные темы."""

    grades: tuple[Grade, ...]
    industries: tuple[Industry, ...]
    specializations: tuple[Specialization, ...]
    technologies: tuple[Technology, ...]
    fsp_disciplines: tuple[FspDiscipline, ...] = ()

    def __post_init__(self) -> None:
        for specialization in self.specializations:
            for topic in specialization.topics:
                if not topic.code.startswith(f"{specialization.code}."):
                    raise ValueError(
                        f"код темы {topic.code} должен начинаться с «{specialization.code}.»"
                    )
        for kind, codes in [
            ("грейд", [g.code for g in self.grades]),
            ("сфера бизнеса", [i.code for i in self.industries]),
            ("специализация", [s.code for s in self.specializations]),
            ("тема", [t.code for t in self.topics()]),
            ("технология", [t.code for t in self.technologies]),
            ("дисциплина ФСП", [d.code for d in self.fsp_disciplines]),
            ("ранг грейда", [str(g.rank) for g in self.grades]),
        ]:
            if dupes := {c for c in codes if codes.count(c) > 1}:
                raise ValueError(f"{kind}: повторяются коды {dupes}")
        known = {t.code for t in self.topics()}
        for tech in self.technologies:
            if unknown := set(tech.topics) - known:
                raise ValueError(f"технология {tech.code} ссылается на неизвестные темы {unknown}")
        for discipline in self.fsp_disciplines:
            if unknown := set(discipline.topics) - known:
                raise ValueError(
                    f"дисциплина ФСП {discipline.code} ссылается на неизвестные темы {unknown}"
                )

    def topics(self) -> Iterable[Topic]:
        return (t for s in self.specializations for t in s.topics)


class CatalogPart(enum.StrEnum):
    """Справочник, у которого синхронизация снимает коды. Порядок — от главных к зависимым."""

    grades = "grades"
    industries = "industries"
    specializations = "specializations"
    topics = "topics"
    technologies = "technologies"
    fsp_disciplines = "fsp_disciplines"


def catalog_codes(catalog: Catalog) -> dict[CatalogPart, set[str]]:
    return {
        CatalogPart.grades: {g.code for g in catalog.grades},
        CatalogPart.industries: {i.code for i in catalog.industries},
        CatalogPart.specializations: {s.code for s in catalog.specializations},
        CatalogPart.topics: {t.code for t in catalog.topics()},
        CatalogPart.technologies: {t.code for t in catalog.technologies},
        CatalogPart.fsp_disciplines: {d.code for d in catalog.fsp_disciplines},
    }


@dataclass(frozen=True)
class CatalogPlan:
    """Что синхронизация меняет в хранилище: записи `catalog` добавляются или обновляются по
    коду, коды из `removed` снимаются, связи технологий и дисциплин с темами заменяются целиком."""

    catalog: Catalog
    removed: Mapping[CatalogPart, frozenset[str]]


def catalog_plan(stored: Mapping[CatalogPart, Collection[str]], catalog: Catalog) -> CatalogPlan:
    """Синхронизация хранилища с кодами `stored` до справочника `catalog`."""
    wanted = catalog_codes(catalog)
    return CatalogPlan(
        catalog,
        {part: frozenset(set(stored.get(part, ())) - wanted[part]) for part in CatalogPart},
    )
