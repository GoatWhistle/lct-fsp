"""Рендер PDF-профиля за портом: на вход — доменная проекция, без базы и HTTP."""

import io
from dataclasses import replace
from datetime import UTC, date, datetime

import pytest
from pypdf import PdfReader

from app.adapter.profile_pdf import FpdfProfileRenderer, years_words
from app.domain.candidate import Disclosed, ProfileSheet, SelfReported
from app.domain.catalog import CatalogRef
from app.domain.experience import ExperienceEntry, Month, TechnologyYears
from app.domain.fsp import ConfirmedAchievement, FspResult
from app.domain.work import WorkFormat
from app.usecase.interface import ProfilePdfRenderer

NOW = datetime(2026, 10, 7, 21, 30, tzinfo=UTC)

SHEET = ProfileSheet(
    disclosed=Disclosed(
        full_name="Ёлкина Юлия Сергеевна",
        contact_email="yulia@example.ru",
        contact_phone=None,
        telegram=None,
        about="",
        job_roles=(),
        soft_skills=(),
    ),
    self_reported=SelfReported(
        stack=(CatalogRef("python", "Python"),),
        experience_years=0,
        work_formats=(WorkFormat.remote,),
        city=None,
        relocation=False,
        industries=(),
    ),
    category=None,
    skill_profile=None,
    grade_confidence=0.8,
)


def test_renders_projection_as_is() -> None:
    renderer: ProfilePdfRenderer = FpdfProfileRenderer()

    content = renderer.render(SHEET, now=NOW)

    text = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(content)).pages)
    assert "Ёлкина Юлия Сергеевна" in text
    assert "меньше года" in text
    assert "Удалённо" in text
    assert "Категория пока не присвоена" in text
    # 8 октября по Москве: в UTC ещё 7-е.
    assert "8 октября 2026" in text


def test_same_projection_and_time_give_same_bytes() -> None:
    renderer = FpdfProfileRenderer()

    assert renderer.render(SHEET, now=NOW) == renderer.render(SHEET, now=NOW)


def text_of(sheet: ProfileSheet) -> str:
    content = FpdfProfileRenderer().render(sheet, now=NOW)
    return "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(content)).pages)


def test_fsp_achievements_are_a_confirmed_block_apart_from_self_description() -> None:
    achievement = ConfirmedAchievement(
        event="Чемпионат России по продуктовому программированию",
        date=date(2025, 4, 12),
        discipline=CatalogRef("product", "Продуктовое программирование"),
        place=2,
        result=FspResult.prize,
        team_role=CatalogRef("qa", "QA"),
    )

    text = text_of(replace(SHEET, fsp_achievements=(achievement,)))

    fsp, self_reported = text.index("ПОДТВЕРЖДЕНО ФСП"), text.index("СО СЛОВ КАНДИДАТА")
    assert fsp < self_reported
    block = text[fsp:self_reported]
    for part in ("12.04.2025", "продуктовому", "призёр", "2 место", "QA"):
        assert part in block


def test_candidate_without_fsp_history_gets_neutral_note() -> None:
    assert "Нет истории ФСП" in text_of(SHEET)


def test_experience_card_is_a_block_from_candidate_words_after_self_description() -> None:
    entry = ExperienceEntry(
        place="ООО «Ромашка»",
        role="QA-инженер",
        start=Month(2021, 3),
        end=None,
        stack=(CatalogRef("python", "Python"),),
        summary="Автотесты платёжного шлюза",
    )
    disclosed = replace(SHEET.disclosed, experience=(entry,))
    sheet = replace(
        SHEET,
        disclosed=disclosed,
        technology_years=(TechnologyYears(CatalogRef("python", "Python"), 5.5),),
    )

    text = text_of(sheet)

    block = text[text.index("ОПЫТ (СО СЛОВ КАНДИДАТА)") :]
    assert text.index("СО СЛОВ КАНДИДАТА") < text.index("ОПЫТ (СО СЛОВ КАНДИДАТА)")
    for part in ("03.2021 — по сейчас", "QA-инженер", "Ромашка", "платёжного", "5,5 года"):
        assert part in block


def test_empty_experience_card_has_no_block() -> None:
    assert "ОПЫТ (СО СЛОВ" not in text_of(SHEET)


@pytest.mark.parametrize(
    ("years", "words"),
    [(0.0, "меньше полугода"), (0.5, "полгода"), (1.0, "1 год"), (2.5, "2,5 года"), (5.0, "5 лет")],
)
def test_years_words(years: float, words: str) -> None:
    assert years_words(years) == words
