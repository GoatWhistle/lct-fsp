from collections.abc import Sequence
from dataclasses import dataclass

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from app.adapter.brand.palette import Color, color
from app.adapter.brand.words import BRAND_DIR, Words
from app.domain.candidate import Level
from app.domain.skill import LevelBand

FONTS = BRAND_DIR / "fonts"
MARK = BRAND_DIR / "fsp-mark.svg"
UI = "Onest"
MONO = "JetBrainsMono"
MARGIN = 18.0
TOP = 30.0
SCALE_PAD = 1.0
ZONE_LABELS = ("below", "intern", "junior", "middle", "senior")


@dataclass(frozen=True)
class Ink:
    text: Color
    secondary: Color
    tertiary: Color
    accent: Color
    hairline: Color
    tint: Color
    track: Color
    band: Color
    level: Color
    threshold: Color
    required: Color
    fsp: Color
    canvas: Color


def ink() -> Ink:
    return Ink(
        text=color("text-primary"),
        secondary=color("text-secondary"),
        tertiary=color("text-tertiary"),
        accent=color("text-accent"),
        hairline=color("border-hairline"),
        tint=color("surface-tint"),
        track=color("data-track"),
        band=color("data-band"),
        level=color("data-level"),
        threshold=color("data-threshold"),
        required=color("data-required"),
        fsp=color("data-fsp"),
        canvas=color("surface-canvas"),
    )


class BrandDocument(FPDF):
    def __init__(self, words: Words, label: str, footer_text: str) -> None:
        super().__init__(format="A4")
        self.words = words
        self.ink = ink()
        self.label = label
        self.footer_text = footer_text
        self.add_font(UI, "", FONTS / "Onest-Regular.ttf")
        self.add_font(UI, "B", FONTS / "Onest-SemiBold.ttf")
        self.add_font(MONO, "", FONTS / "JetBrainsMono-Regular.ttf")
        self.add_font(MONO, "B", FONTS / "JetBrainsMono-Bold.ttf")
        self.set_margins(MARGIN, TOP, MARGIN)
        self.set_auto_page_break(auto=True, margin=22)

    def header(self) -> None:
        self.image(str(MARK), x=self.l_margin, y=11, h=8)
        self.set_xy(self.l_margin + 10.5, 11.6)
        self.set_font(MONO, "B", 14)
        self.set_text_color(*self.ink.text)
        self.cell(0, 7, self.words("brand.name"))
        self.set_xy(self.l_margin, 11.6)
        self.set_font(UI, "", 9)
        self.set_text_color(*self.ink.secondary)
        self.cell(0, 7, self.label, align="R")
        self.set_draw_color(*self.ink.hairline)
        self.set_line_width(0.2)
        self.line(self.l_margin, 22, self.w - self.r_margin, 22)
        self.set_y(TOP)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_draw_color(*self.ink.hairline)
        self.set_line_width(0.2)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(1.5)
        self.set_font(UI, "", 8)
        self.set_text_color(*self.ink.tertiary)
        self.cell(self.epw * 0.75, 5, self.footer_text)
        page = self.words("pdf.page", page=self.page_no(), total="{nb}")
        self.set_font(MONO, "", 8)
        self.cell(0, 5, page, align="R")


def text(
    doc: BrandDocument,
    value: str,
    *,
    size: float,
    mono: bool = False,
    bold: bool = False,
    tone: Color | None = None,
    height: float | None = None,
) -> None:
    doc.set_font(MONO if mono else UI, "B" if bold else "", size)
    doc.set_text_color(*(tone or doc.ink.text))
    line = height if height is not None else size * 0.5
    doc.multi_cell(0, line, value, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def section(doc: BrandDocument, title: str) -> None:
    if doc.get_y() > doc.h - 60:
        doc.add_page()
    doc.ln(7)
    y = doc.get_y()
    doc.set_fill_color(*doc.ink.accent)
    doc.ellipse(doc.l_margin, y + 1.6, 2.2, 2.2, style="F")
    doc.set_xy(doc.l_margin + 4.2, y)
    doc.set_font(MONO, "B", 9.5)
    doc.set_text_color(*doc.ink.accent)
    caption = title.upper()
    doc.cell(doc.get_string_width(caption) + 2, 5.4, caption)
    start = doc.get_x() + 1
    doc.set_draw_color(*doc.ink.hairline)
    doc.set_line_width(0.3)
    doc.line(start, y + 2.7, doc.w - doc.r_margin, y + 2.7)
    doc.set_y(y + 9)


def pill_width(doc: BrandDocument, value: str, size: float = 8.5) -> float:
    doc.set_font(UI, "", size)
    return doc.get_string_width(value) + 5.2


def pill(
    doc: BrandDocument,
    value: str,
    x: float,
    y: float,
    *,
    fill: Color,
    tone: Color,
    size: float = 8.5,
) -> float:
    width = pill_width(doc, value, size)
    doc.set_fill_color(*fill)
    doc.rect(x, y, width, 5.4, style="F", round_corners=True, corner_radius=2.7)
    doc.set_xy(x, y)
    doc.set_font(UI, "", size)
    doc.set_text_color(*tone)
    doc.cell(width, 5.4, value, align="C")
    return width


def pills(doc: BrandDocument, values: Sequence[str], *, fill: Color, tone: Color) -> None:
    x, y = doc.l_margin, doc.get_y()
    for value in values:
        width = pill_width(doc, value)
        if x + width > doc.w - doc.r_margin:
            x, y = doc.l_margin, y + 7
        pill(doc, value, x, y, fill=fill, tone=tone)
        x += width + 2
    doc.set_xy(doc.l_margin, y + 8)


def terms(doc: BrandDocument, rows: Sequence[tuple[str, str]], label_width: float = 42) -> None:
    for label, value in rows:
        y = doc.get_y()
        doc.set_xy(doc.l_margin, y)
        doc.set_font(UI, "", 9)
        doc.set_text_color(*doc.ink.tertiary)
        doc.multi_cell(label_width, 5, label)
        label_end = doc.get_y()
        doc.set_xy(doc.l_margin + label_width, y)
        doc.set_font(UI, "", 10)
        doc.set_text_color(*doc.ink.text)
        doc.multi_cell(0, 5, value, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        doc.set_y(max(label_end, doc.get_y()) + 1.2)


def _scale(level: Level) -> tuple[float, float]:
    values = [threshold for _, threshold in level.thresholds]
    return min(values) - SCALE_PAD, max(values) + SCALE_PAD


def _at(value: float, low: float, high: float, x: float, width: float) -> float:
    share = (min(high, max(low, value)) - low) / (high - low)
    return x + share * width


def ruler(
    doc: BrandDocument,
    level: Level,
    x: float,
    y: float,
    width: float,
    *,
    labels: bool,
    required: float | None = None,
) -> float:
    low, high = _scale(level)
    height = 3.2 if labels else 2.4
    doc.set_fill_color(*doc.ink.track)
    doc.rect(x, y, width, height, style="F", round_corners=True, corner_radius=height / 2)
    doc.set_draw_color(*doc.ink.threshold)
    doc.set_line_width(0.25)
    for _, threshold in level.thresholds:
        tick = _at(threshold, low, high, x, width)
        doc.line(tick, y - 0.4, tick, y + height + 0.4)
    band_start = _at(level.theta - level.theta_sd, low, high, x, width)
    band_end = _at(level.theta + level.theta_sd, low, high, x, width)
    doc.set_fill_color(*doc.ink.band)
    doc.rect(
        band_start,
        y,
        max(band_end - band_start, height),
        height,
        style="F",
        round_corners=True,
        corner_radius=height / 2,
    )
    if required is not None:
        mark = _at(required, low, high, x, width)
        doc.set_draw_color(*doc.ink.required)
        doc.set_line_width(0.5)
        doc.line(mark, y - 1, mark, y + height + 1)
    node = _at(level.theta, low, high, x, width)
    doc.set_fill_color(*doc.ink.level)
    doc.set_draw_color(255, 255, 255)
    doc.set_line_width(0.4)
    doc.ellipse(node - height * 0.75, y - height * 0.25, height * 1.5, height * 1.5, style="DF")
    if not labels:
        return y + height
    edges = [low, *(threshold for _, threshold in level.thresholds), high]
    doc.set_font(MONO, "", 7.5)
    doc.set_text_color(*doc.ink.tertiary)
    for index, zone in enumerate(ZONE_LABELS):
        start = _at(edges[index], low, high, x, width)
        end = _at(edges[index + 1], low, high, x, width)
        name = (
            doc.words("pdf.skills.below") if zone == "below" else doc.words.catalog("grade", zone)
        )
        doc.set_xy(start, y + height + 1.2)
        doc.cell(end - start, 4, name, align="C")
    return y + height + 5.5


def level_words(words: Words, band: LevelBand) -> str:
    def grade(code: str) -> str:
        if code == "intern":
            return words("pdf.level.internLower")
        return words.catalog("grade", code)

    if band.low == band.high:
        if band.low is None:
            return words("pdf.level.below")
        return words("pdf.level.confident", grade=grade(band.low))
    if not band.low:
        return words("pdf.level.internOrBelow")
    low = words("pdf.level.internWith") if band.low == "intern" else grade(band.low)
    return words("pdf.level.between", low=low, high=grade(band.high or ""))


def uncertainty_words(words: Words, sd: float) -> str:
    size = "small" if sd < 0.35 else "medium" if sd < 0.7 else "large"
    return words(f"pdf.uncertainty.{size}")
