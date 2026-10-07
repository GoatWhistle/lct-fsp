"""Рендер PDF-профиля за портом: на вход — доменная проекция, без базы и HTTP."""

import io
from datetime import UTC, datetime

from pypdf import PdfReader

from app.adapter.profile_pdf import FpdfProfileRenderer
from app.domain.candidate import Disclosed, ProfileSheet, SelfReported
from app.domain.catalog import CatalogRef
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
