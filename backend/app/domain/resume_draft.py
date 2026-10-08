"""Черновик анкеты из резюме в PDF и подсказка грейда (mechanics.md, §16; docs/adr/0002).

Порт `TextUnderstanding` превращает очищенный текст резюме в черновик анкеты. Адаптеру сценарий
не доверяет: всё, чего нет в справочнике или что не похоже на своё поле, отбрасывает
`checked_resume`. Черновик — не профиль: в профиль он попадает только формой, которую кандидат
проверил и сохранил, и только самоописанием — низшим уровнем доверия.

Подсказка грейда — по стажу и ролям. Выбирает грейд кандидат, категорию определяет только тест:
подсказка ни на что, кроме экрана выбора грейда, не влияет.
"""

import enum
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.domain.catalog import Catalog, CatalogRef, Grade

# Длина полей — как у формы профиля.
FULL_NAME_MAX = 200
EMAIL_MAX = 254
PHONE_MAX = 32
ROLE_MAX = 100
ROLES_MAX = 10
SOFT_SKILL_MAX = 50
SOFT_SKILLS_MAX = 15
EXPERIENCE_MAX = 60

_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_PHONE = re.compile(r"\+?[\d ()-]{7,}")
_TELEGRAM = re.compile(r"[A-Za-z0-9_]{5,32}")


class ResumeField(enum.StrEnum):
    full_name = "full_name"
    contact_email = "contact_email"
    contact_phone = "contact_phone"
    telegram = "telegram"
    stack = "stack"
    job_roles = "job_roles"
    experience_years = "experience_years"
    soft_skills = "soft_skills"


@dataclass(frozen=True)
class ResumeDraft:
    """Что адаптер узнал в резюме: стек — кодами справочника, стаж — полных лет. Чего в тексте
    нет, то `None` или пусто."""

    full_name: str | None
    contact_email: str | None
    contact_phone: str | None
    telegram: str | None
    stack: tuple[str, ...]
    job_roles: tuple[str, ...]
    experience_years: int | None
    soft_skills: tuple[str, ...]
    # Уверенность по полю в [0, 1]; `None` или нет ключа — адаптер её не считает.
    confidence: Mapping[ResumeField, float | None]


EMPTY_RESUME = ResumeDraft(None, None, None, None, (), (), None, (), {})


@dataclass(frozen=True)
class GradeHintRule:
    """Из чего подсказка грейда: стаж в годах, с которого начинается грейд, и слова в ролях,
    которые называют грейд («тимлид», «стажёр»). Звёздочка в конце слова — основа слова."""

    experience_years: Mapping[str, int]
    role_words: Mapping[str, Sequence[str]]


@dataclass(frozen=True)
class GradeHint:
    """Подсказка — младший из грейдов по стажу и по ролям: оба основания видны кандидату."""

    grade: CatalogRef
    by_experience: CatalogRef | None
    by_roles: CatalogRef | None


@dataclass(frozen=True)
class CheckedResumeDraft:
    """Черновик после проверки — то, что видит экран «система поняла так»."""

    full_name: str | None
    contact_email: str | None
    contact_phone: str | None
    telegram: str | None
    # В порядке справочника.
    stack: tuple[CatalogRef, ...]
    job_roles: tuple[str, ...]
    experience_years: int | None
    soft_skills: tuple[str, ...]
    confidence: Mapping[ResumeField, float | None]
    # Распознанные поля с уверенностью ниже порога — экран их подсвечивает.
    uncertain: frozenset[ResumeField]
    grade_hint: GradeHint | None


def _line(value: object, limit: int) -> str | None:
    """Строка в одну строку не длиннее `limit`; не строка или длиннее — как если бы поля не
    было: обрезанное ФИО или телефон хуже пустого."""
    if not isinstance(value, str):
        return None
    value = " ".join(value.split())
    return value if 0 < len(value) <= limit else None


def _matching(value: object, limit: int, pattern: re.Pattern[str]) -> str | None:
    line = _line(value, limit)
    return line if line is not None and pattern.fullmatch(line) else None


def _tags(values: object, limit: int, count: int) -> tuple[str, ...]:
    """Метки без пустых и повторов без учёта регистра, не больше `count`."""
    if not isinstance(values, list | tuple):
        return ()
    seen: set[str] = set()
    tags = []
    for value in values:
        tag = _line(value, limit)
        if tag is not None and tag.casefold() not in seen:
            seen.add(tag.casefold())
            tags.append(tag)
    return tuple(tags[:count])


def _confidence(given: object) -> float | None:
    """Уверенность вне [0, 1] или не числом — как если бы адаптер её не считал."""
    if isinstance(given, int | float) and not isinstance(given, bool) and 0 <= given <= 1:
        return float(given)
    return None


def checked_resume(
    draft: ResumeDraft, catalog: Catalog, *, confident: float, rule: GradeHintRule
) -> CheckedResumeDraft:
    """Черновик в пределах справочника и формы: неизвестные коды стека, контакты не своего
    вида, стаж вне [0, 60] и значения не того типа отбрасываются, а не роняют разбор. Поле с
    уверенностью ниже `confident` — неуверенное."""
    asked_stack = (
        {c for c in draft.stack if isinstance(c, str)}
        if isinstance(draft.stack, list | tuple)
        else set()
    )
    stack = tuple(CatalogRef(t.code, t.name) for t in catalog.technologies if t.code in asked_stack)
    full_name = _line(draft.full_name, FULL_NAME_MAX)
    email = _matching(draft.contact_email, EMAIL_MAX, _EMAIL)
    phone = _matching(draft.contact_phone, PHONE_MAX, _PHONE)
    telegram = _line(draft.telegram, 33)
    telegram = telegram.removeprefix("@") if telegram else None
    telegram = telegram if telegram and _TELEGRAM.fullmatch(telegram) else None
    roles = _tags(draft.job_roles, ROLE_MAX, ROLES_MAX)
    soft_skills = _tags(draft.soft_skills, SOFT_SKILL_MAX, SOFT_SKILLS_MAX)
    experience = draft.experience_years
    experience = (
        experience if type(experience) is int and 0 <= experience <= EXPERIENCE_MAX else None
    )
    recognized = {
        ResumeField.full_name: full_name is not None,
        ResumeField.contact_email: email is not None,
        ResumeField.contact_phone: phone is not None,
        ResumeField.telegram: telegram is not None,
        ResumeField.stack: bool(stack),
        ResumeField.job_roles: bool(roles),
        ResumeField.experience_years: experience is not None,
        ResumeField.soft_skills: bool(soft_skills),
    }
    given = draft.confidence if isinstance(draft.confidence, Mapping) else {}
    confidence = {name: _confidence(given.get(name)) for name, found in recognized.items() if found}
    return CheckedResumeDraft(
        full_name=full_name,
        contact_email=email.lower() if email else None,
        contact_phone=phone,
        telegram=telegram,
        stack=stack,
        job_roles=roles,
        experience_years=experience,
        soft_skills=soft_skills,
        confidence=confidence,
        uncertain=frozenset(
            name for name, level in confidence.items() if level is not None and level < confident
        ),
        grade_hint=grade_hint(experience, roles, catalog.grades, rule),
    )


def _words(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower().replace("ё", "е"))


def _names(role: list[str], word: str) -> bool:
    """Есть ли в словах роли слово или фраза `word`; звёздочка в конце — основа слова."""
    stem = word.endswith("*")
    parts = _words(word.rstrip("*"))
    if not parts:
        return False
    for start in range(len(role) - len(parts) + 1):
        window = role[start : start + len(parts)]
        *head, last = window
        if head == parts[:-1] and (last.startswith(parts[-1]) if stem else last == parts[-1]):
            return True
    return False


def grade_hint(
    experience_years: int | None,
    job_roles: Sequence[str],
    grades: Sequence[Grade],
    rule: GradeHintRule,
) -> GradeHint | None:
    """Грейд по стажу — старший грейд, чей порог стажа не выше стажа, иначе младший грейд
    справочника; по ролям — старший грейд, названный в ролях. Подсказка — младший из двух: она
    помогает не замахнуться выше, чем говорит опыт, а проверяет всё равно тест. Без стажа и
    без грейда в ролях подсказки нет."""
    ordered = sorted(grades, key=lambda g: g.rank)
    if not ordered:
        return None
    by_experience = None
    if experience_years is not None:
        reached = [g for g in ordered if rule.experience_years.get(g.code, 0) <= experience_years]
        by_experience = reached[-1] if reached else ordered[0]
    words = [_words(role) for role in job_roles]
    named = [
        g
        for g in ordered
        if any(_names(role, w) for role in words for w in rule.role_words.get(g.code, ()))
    ]
    by_roles = named[-1] if named else None
    found = [g for g in (by_experience, by_roles) if g is not None]
    if not found:
        return None
    hint = min(found, key=lambda g: g.rank)
    return GradeHint(
        grade=_ref(hint),
        by_experience=_ref(by_experience) if by_experience else None,
        by_roles=_ref(by_roles) if by_roles else None,
    )


def _ref(grade: Grade) -> CatalogRef:
    return CatalogRef(grade.code, grade.name)
