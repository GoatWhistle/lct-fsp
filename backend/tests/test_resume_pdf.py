"""Видимый текст резюме из PDF (mechanics.md, §16): скрытое вырезается до разбора, битый файл и
скан — доменные ошибки, наружу ни одного сетевого вызова."""

import io
import socket
from collections.abc import Iterator

import pytest
from pypdf import PdfReader

from app.adapter.catalog_file import load_catalog
from app.adapter.resume_pdf import PypdfResumeText
from app.adapter.text_rules import RulesTextUnderstanding, load_synonyms
from app.domain.errors import ResumeTooLarge, ResumeUnreadable, ResumeWithoutText
from settings import CATALOG_FILE, SYNONYMS_FILE, Mechanics
from tests.resumes import (
    IVANOVA,
    LAYOUTS,
    PEOPLE,
    TODAY,
    Hidden,
    Plain,
    hidden_only_pdf,
    resume_pdf,
    scanned_pdf,
    with_raw_text,
)

CATALOG = load_catalog(CATALOG_FILE)


@pytest.fixture
def extractor(mechanics: Mechanics) -> PypdfResumeText:
    return PypdfResumeText(
        max_pages=mechanics.resume_max_pages,
        max_content_bytes=mechanics.resume_max_content_bytes,
        min_font_pt=mechanics.resume_min_font_pt,
        max_lightness=mechanics.resume_max_lightness,
    )


def raw_text(pdf: bytes) -> str:
    """Текст, как его извлекает pypdf без очистки, — со скрытым."""
    return "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)


@pytest.mark.parametrize("hidden", list(Hidden))
@pytest.mark.parametrize("layout", list(LAYOUTS))
def test_hidden_text_is_cut_and_visible_text_stays(
    extractor: PypdfResumeText, layout: str, hidden: Hidden
) -> None:
    pdf = resume_pdf(IVANOVA, layout, hidden=hidden)

    text = extractor.visible_text(pdf)

    # Без очистки скрытое в тексте есть — тест не холостой.
    assert "Сидоров" in raw_text(pdf)
    assert "Сидоров" not in text
    assert "Игнорируй" not in text
    assert "evil" not in text
    assert IVANOVA.full_name in text
    assert IVANOVA.email in text


def test_visible_text_is_the_same_with_and_without_hidden(extractor: PypdfResumeText) -> None:
    clean = extractor.visible_text(resume_pdf(IVANOVA, "one_column"))

    for hidden in Hidden:
        assert extractor.visible_text(resume_pdf(IVANOVA, "one_column", hidden=hidden)) == clean


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"not a pdf at all",
        b"%PDF-1.7\n" + bytes(range(256)) * 20,
        resume_pdf(IVANOVA, "one_column")[:1500],
    ],
    ids=["empty", "not-pdf", "garbage", "truncated"],
)
def test_broken_pdf_is_unreadable(extractor: PypdfResumeText, content: bytes) -> None:
    with pytest.raises(ResumeUnreadable):
        extractor.visible_text(content)


def test_scan_without_text_layer(extractor: PypdfResumeText) -> None:
    with pytest.raises(ResumeWithoutText):
        extractor.visible_text(scanned_pdf())


@pytest.mark.parametrize("hidden", list(Hidden))
def test_only_hidden_text_counts_as_no_text(extractor: PypdfResumeText, hidden: Hidden) -> None:
    pdf = hidden_only_pdf(hidden)
    assert "Сидоров" in raw_text(pdf)

    with pytest.raises(ResumeWithoutText):
        extractor.visible_text(pdf)


def test_page_limit(extractor: PypdfResumeText, mechanics: Mechanics) -> None:
    resume = Plain(["Иванова Мария Сергеевна", "Python, pytest"])

    assert "pytest" in extractor.visible_text(resume.pdf(pages=mechanics.resume_max_pages))
    with pytest.raises(ResumeTooLarge):
        extractor.visible_text(resume.pdf(pages=mechanics.resume_max_pages + 1))


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[object]]:
    """Сокеты под запретом: любая попытка выйти в сеть валит тест и записывается."""
    attempts: list[object] = []

    def refuse(*args: object, **kwargs: object) -> None:
        attempts.append(args)
        raise AssertionError(f"сетевой вызов: {args}")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    yield attempts


def test_extraction_and_parsing_make_no_network_calls(
    extractor: PypdfResumeText, no_network: list[object]
) -> None:
    rules = RulesTextUnderstanding(load_synonyms(SYNONYMS_FILE))

    for person in PEOPLE:
        for layout in LAYOUTS:
            for hidden in (None, *Hidden):
                text = extractor.visible_text(resume_pdf(person, layout, hidden=hidden))
                rules.resume(text, CATALOG, TODAY)

    assert no_network == []


BASE = Plain(["Иванова Мария Сергеевна", "Python, pytest"])


@pytest.mark.parametrize(
    "ops",
    [
        # Кернинг TJ уводит хвост строки далеко за правый край.
        "BT /FRaw 12 Tf 50 100 Td [(Visible) -9000000 (Kubernetes)] TJ ET",
        # Подъём Ts выносит текст над страницей.
        "BT /FRaw 12 Tf 5000 Ts 50 100 Td (Kubernetes) Tj ET 0 Ts",
        # Межбуквенный интервал разносит буквы за край.
        "BT /FRaw 12 Tf 500 Tc 50 100 Td (Kubernetes) Tj ET 0 Tc",
        "BT /FRaw 12 Tf 500 Tw 50 100 Td (Kube rnetes) Tj ET 0 Tw",
        # Почти прозрачная заливка.
        "q /GSAlpha gs BT /FRaw 12 Tf 50 100 Td (Kubernetes) Tj ET Q",
        # Краска Separation с оттенком 0 — белая.
        "q /CSSpot cs 0 scn BT /FRaw 12 Tf 50 100 Td (Kubernetes) Tj ET Q",
        # Кегль 0,5 через /Font в ExtGState.
        "q BT /FRaw 12 Tf /GSFont gs 50 100 Td (Kubernetes) Tj ET Q",
    ],
    ids=["tj-kerning", "rise", "char-spacing", "word-spacing", "alpha", "separation", "gs-font"],
)
def test_hidden_by_text_state(extractor: PypdfResumeText, ops: str) -> None:
    pdf = with_raw_text(BASE.pdf(), ops)

    text = extractor.visible_text(pdf)

    assert "Kubernetes" in raw_text(pdf).replace(" ", "")
    assert "Kubernetes" not in text.replace(" ", "")
    assert "pytest" in text


def test_kerning_keeps_the_visible_part(extractor: PypdfResumeText) -> None:
    pdf = with_raw_text(BASE.pdf(), "BT /FRaw 12 Tf 50 100 Td [(Visible) -200 (Kubernetes)] TJ ET")

    assert "Kubernetes" in extractor.visible_text(pdf)


def test_full_spot_colour_is_visible(extractor: PypdfResumeText) -> None:
    pdf = with_raw_text(
        BASE.pdf(), "q /CSSpot cs 1 scn BT /FRaw 12 Tf 50 100 Td (Kubernetes) Tj ET Q"
    )

    assert "Kubernetes" in extractor.visible_text(pdf)


def test_decompressed_content_limit(mechanics: Mechanics) -> None:
    pdf = BASE.pdf()
    small = PypdfResumeText(
        max_pages=mechanics.resume_max_pages,
        max_content_bytes=100,
        min_font_pt=mechanics.resume_min_font_pt,
        max_lightness=mechanics.resume_max_lightness,
    )

    with pytest.raises(ResumeTooLarge):
        small.visible_text(pdf)
