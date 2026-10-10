from collections.abc import Sequence
from datetime import datetime, timedelta, timezone

from fpdf.enums import XPos, YPos

from app.adapter.brand.pdf_kit import (
    MARK,
    MONO,
    UI,
    BrandDocument,
    card,
    fsp_pill,
    level_words,
    pill,
    pills,
    ruler,
    section,
    terms,
    text,
    tile,
    uncertainty_words,
)
from app.adapter.brand.words import Words
from app.domain.candidate import (
    Category,
    Disclosed,
    ProfileSheet,
    SelfReported,
    SkillProfile,
    TopicLevel,
)
from app.domain.experience import ExperienceEntry, Month, TechnologyYears
from app.domain.fsp import ConfirmedAchievement
from app.domain.locale import DEFAULT_LOCALE, Locale

MOSCOW = timezone(timedelta(hours=3), "MSK")
TOPIC_COLUMN = 74.0
RULER_WIDTH = 64.0
CATEGORY_WIDTH = 62.0
CATEGORY_HEIGHT = 36.0
HERO_GAP = 8.0
CONTACT_LABEL = 22.0
TILE_GAP = 3.0
TILE_HEIGHT = 19.0
FSP_BADGE = 9.0
FSP_INDENT = 13.0
STACK_LABEL = 42.0


class FpdfProfileRenderer:
    def render(
        self, sheet: ProfileSheet, *, now: datetime, locale: Locale = DEFAULT_LOCALE
    ) -> bytes:
        words = Words(locale)
        generated = words("pdf.generated", date=words.date(now.astimezone(MOSCOW).date()))
        footer = f"{words('brand.name')}. {words('brand.tagline')}. {generated}"
        doc = BrandDocument(words, words("pdf.label"), footer)
        disclosed = sheet.disclosed
        doc.set_title(words("pdf.documentTitle", name=disclosed.full_name))
        doc.set_author(disclosed.full_name)
        doc.set_creator(words("brand.name"))
        doc.set_lang(locale)
        doc.set_creation_date(now)
        doc.add_page()
        _hero(doc, sheet)
        _verified(doc, sheet.skill_profile, sheet.grade_confidence)
        _fsp(doc, sheet.fsp_achievements)
        _self_reported(doc, sheet.self_reported, disclosed)
        _experience(doc, disclosed.experience, sheet.technology_years)
        return bytes(doc.output())


def _caption(doc: BrandDocument, value: str) -> None:
    text(doc, value, size=7.5, mono=True, tone=doc.ink.tertiary, height=4)


def _capital(value: str) -> str:
    return value[:1].upper() + value[1:]


def _hero(doc: BrandDocument, sheet: ProfileSheet) -> None:
    words = doc.words
    disclosed = sheet.disclosed
    top = doc.get_y()
    left = doc.epw - CATEGORY_WIDTH - HERO_GAP
    doc.set_font(UI, "B", 22)
    doc.set_text_color(*doc.ink.text)
    doc.multi_cell(left, 9.5, disclosed.full_name, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if disclosed.job_roles:
        doc.ln(1.5)
        pills(
            doc,
            disclosed.job_roles,
            fill=doc.ink.tint,
            tone=doc.ink.accent,
            right=doc.l_margin + left,
        )
    telegram = f"@{disclosed.telegram}" if disclosed.telegram else ""
    contacts = [
        (words("pdf.contacts.email"), disclosed.contact_email),
        (words("pdf.contacts.phone"), disclosed.contact_phone or ""),
        (words("pdf.contacts.telegram"), telegram),
    ]
    doc.ln(1)
    for label, value in contacts:
        if not value:
            continue
        doc.set_x(doc.l_margin)
        doc.set_font(MONO, "", 7.5)
        doc.set_text_color(*doc.ink.tertiary)
        doc.cell(CONTACT_LABEL, 5.5, label)
        doc.set_font(UI, "", 10)
        doc.set_text_color(*doc.ink.text)
        doc.cell(left - CONTACT_LABEL, 5.5, value, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    bottom = doc.get_y()
    _category_card(doc, sheet.category, doc.l_margin + left + HERO_GAP, top)
    doc.set_y(max(bottom, top + CATEGORY_HEIGHT) + 6)
    _summary(doc, sheet)


def _category_card(doc: BrandDocument, category: Category | None, x: float, y: float) -> None:
    words = doc.words
    inner = CATEGORY_WIDTH - 10
    card(doc, x, y, CATEGORY_WIDTH, CATEGORY_HEIGHT, doc.ink.tint)
    doc.set_xy(x + 5, y + 4.5)
    doc.set_font(MONO, "", 7.5)
    doc.set_text_color(*doc.ink.accent)
    doc.cell(inner, 4, words("pdf.category.label").upper())
    if category is None:
        doc.set_xy(x + 5, y + 10.5)
        doc.set_font(UI, "", 9)
        doc.set_text_color(*doc.ink.secondary)
        doc.multi_cell(inner, 4.6, words("pdf.category.none"), align="L")
        return
    doc.set_xy(x + 5, y + 10)
    doc.set_font(MONO, "B", 16)
    doc.set_text_color(*doc.ink.text)
    doc.cell(inner, 8, words.catalog("specialization", category.specialization))
    doc.set_xy(x + 5, y + 18)
    doc.set_text_color(*doc.ink.accent)
    doc.cell(inner, 8, words.catalog("grade", category.grade))
    day = words.date(category.assigned_at.astimezone(MOSCOW).date())
    doc.set_xy(x + 5, y + 27.5)
    doc.set_font(UI, "", 8)
    doc.set_text_color(*doc.ink.secondary)
    doc.multi_cell(inner, 4, words("pdf.category.assigned", date=day), align="L")


def _summary(doc: BrandDocument, sheet: ProfileSheet) -> None:
    words = doc.words
    skills = sheet.skill_profile
    pending = words("pdf.summary.pending")
    achievements = len(sheet.fsp_achievements)
    tiles = [
        (
            words("pdf.skills.overall"),
            level_words(words, skills.overall.band) if skills else pending,
        ),
        (
            words("pdf.summary.precision"),
            words(f"pdf.summary.{_precision(skills.overall.theta_sd)}") if skills else pending,
        ),
        (
            words("pdf.summary.fsp"),
            str(achievements) if achievements else words("pdf.summary.none"),
        ),
        (words("pdf.self.experience"), words.years(sheet.self_reported.experience_years)),
    ]
    y = doc.get_y()
    width = (doc.epw - TILE_GAP * (len(tiles) - 1)) / len(tiles)
    for index, (label, value) in enumerate(tiles):
        x = doc.l_margin + index * (width + TILE_GAP)
        tile(doc, x, y, width, TILE_HEIGHT, label, _capital(value))
    doc.set_y(y + TILE_HEIGHT)


def _precision(sd: float) -> str:
    return "high" if sd < 0.35 else "medium" if sd < 0.7 else "low"


def _verified(doc: BrandDocument, skills: SkillProfile | None, confidence: float) -> None:
    words = doc.words
    section(doc, words("pdf.sections.verified"))
    if skills is None:
        text(doc, words("pdf.skills.pending"), size=10, tone=doc.ink.secondary, height=5.5)
        return
    _caption(doc, words("pdf.skills.overall"))
    overall = skills.overall
    caption = f"{level_words(words, overall.band)}, {uncertainty_words(words, overall.theta_sd)}"
    text(doc, _capital(caption), size=10.5, bold=True, height=6)
    doc.set_y(ruler(doc, overall, doc.l_margin, doc.get_y() + 2, doc.epw, labels=True) + 4)
    _caption(doc, words("pdf.skills.label"))
    doc.ln(1)
    for row in skills.topics:
        _topic(doc, row)
    doc.ln(2)
    note = words("pdf.skills.note", confidence=round(confidence * 100))
    text(doc, note, size=8, tone=doc.ink.tertiary, height=4)


def _topic(doc: BrandDocument, row: TopicLevel) -> None:
    if doc.get_y() > doc.h - 34:
        doc.add_page()
    y = doc.get_y()
    doc.set_draw_color(*doc.ink.hairline)
    doc.set_line_width(0.2)
    doc.line(doc.l_margin, y, doc.w - doc.r_margin, y)
    doc.set_xy(doc.l_margin, y + 1.8)
    doc.set_font(UI, "", 9.5)
    doc.set_text_color(*doc.ink.text)
    doc.multi_cell(TOPIC_COLUMN - 4, 4.6, doc.words.catalog("topic", row.topic), align="L")
    doc.set_x(doc.l_margin)
    doc.set_font(MONO, "", 7.5)
    doc.set_text_color(*doc.ink.secondary)
    doc.multi_cell(TOPIC_COLUMN - 4, 4, level_words(doc.words, row.level.band), align="L")
    bottom = doc.get_y()
    ruler(doc, row.level, doc.l_margin + TOPIC_COLUMN, y + 4.4, RULER_WIDTH, labels=False)
    x = doc.l_margin + TOPIC_COLUMN + RULER_WIDTH + 5
    for source in sorted(row.sources):
        label = doc.words(f"pdf.sources.{source}")
        if source == "fsp":
            x += fsp_pill(doc, label, x, y + 3) + 1.5
        else:
            x += pill(doc, label, x, y + 3, fill=doc.ink.tint, tone=doc.ink.accent, size=7.5) + 1.5
    doc.set_y(max(bottom, y + 9.5) + 1.6)


def _fsp(doc: BrandDocument, achievements: Sequence[ConfirmedAchievement]) -> None:
    words = doc.words
    section(doc, words("pdf.sections.fsp"))
    if not achievements:
        text(doc, words("pdf.fsp.empty"), size=10, tone=doc.ink.secondary, height=5.5)
        return
    indent = doc.l_margin + FSP_INDENT
    for item in achievements:
        if doc.get_y() > doc.h - 40:
            doc.add_page()
        y = doc.get_y()
        card(doc, doc.l_margin, y, FSP_BADGE, FSP_BADGE, doc.ink.tint)
        doc.image(str(MARK), x=doc.l_margin + 1.8, y=y + 1.8, h=FSP_BADGE - 3.6)
        result = words.catalog("fspResult", item.result.value)
        width = pill(doc, result, indent, y, fill=doc.ink.tint, tone=doc.ink.fsp)
        doc.set_xy(indent + width + 3, y)
        doc.set_font(MONO, "", 8.5)
        doc.set_text_color(*doc.ink.secondary)
        doc.cell(0, 5.4, item.date.strftime("%d.%m.%Y"))
        doc.set_xy(indent, y + 6.6)
        doc.set_font(UI, "B", 10.5)
        doc.set_text_color(*doc.ink.text)
        doc.multi_cell(0, 5.2, item.event, align="L")
        details = [words.catalog("discipline", item.discipline)]
        if item.place is not None:
            details.append(words("pdf.fsp.place", place=item.place))
        if item.team_role is not None:
            details.append(words("pdf.fsp.role", role=item.team_role.name))
        doc.set_x(indent)
        doc.set_font(UI, "", 9.5)
        doc.set_text_color(*doc.ink.secondary)
        doc.multi_cell(0, 5, ", ".join(details), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        doc.set_y(doc.get_y() + 3.5)
    text(doc, words("pdf.fsp.note"), size=8, tone=doc.ink.tertiary, height=4)


def _self_reported(doc: BrandDocument, profile: SelfReported, disclosed: Disclosed) -> None:
    words = doc.words
    section(doc, words("pdf.sections.self"))
    if profile.stack:
        y = doc.get_y()
        doc.set_font(UI, "", 9)
        doc.set_text_color(*doc.ink.tertiary)
        doc.cell(STACK_LABEL, 5.4, words("pdf.self.stack"))
        doc.set_y(y)
        pills(
            doc,
            [t.name for t in profile.stack],
            fill=doc.ink.canvas,
            tone=doc.ink.text,
            left=doc.l_margin + STACK_LABEL,
        )
        doc.ln(0.5)
    formats = ", ".join(words.catalog("workFormat", f.value) for f in profile.work_formats)
    industries = ", ".join(words.catalog("industry", i) for i in profile.industries)
    rows = [
        (words("pdf.self.experience"), words.years(profile.experience_years)),
        (words("pdf.self.soft"), _capital(", ".join(disclosed.soft_skills))),
        (words("pdf.self.formats"), _capital(formats)),
        (words("pdf.self.city"), _city(words, profile)),
        (words("pdf.self.industries"), industries),
    ]
    terms(doc, [(label, value) for label, value in rows if value], label_width=STACK_LABEL)
    if disclosed.about:
        doc.ln(2)
        _caption(doc, words("pdf.self.about"))
        text(doc, disclosed.about, size=10, height=5)


def _city(words: Words, profile: SelfReported) -> str:
    if profile.city is None:
        return ""
    relocation = words("pdf.self.relocationYes" if profile.relocation else "pdf.self.relocationNo")
    return f"{profile.city}, {relocation}"


def _experience(
    doc: BrandDocument, entries: Sequence[ExperienceEntry], years: Sequence[TechnologyYears]
) -> None:
    if not entries:
        return
    words = doc.words
    section(doc, words("pdf.sections.experience"))
    for entry in entries:
        period = period_words(entry.start, entry.end, words)
        text(doc, period, size=8.5, mono=True, tone=doc.ink.secondary, height=4.5)
        title = ", ".join(part for part in (entry.role, entry.place) if part)
        text(doc, title, size=10.5, bold=True, height=5.4)
        if entry.stack:
            doc.ln(0.8)
            pills(doc, [t.name for t in entry.stack], fill=doc.ink.canvas, tone=doc.ink.secondary)
        if entry.summary:
            text(doc, entry.summary, size=9.5, height=4.8)
        doc.ln(3)
    if years:
        listed = ", ".join(f"{y.technology.name} {words.half_years(y.years)}" for y in years)
        terms(doc, [(words("pdf.experience.technologyYears"), listed)], label_width=STACK_LABEL)
    doc.ln(1)
    text(doc, words("pdf.experience.note"), size=8, tone=doc.ink.tertiary, height=4)


def _month(month: Month) -> str:
    return f"{month.month:02d}.{month.year}"


def period_words(start: Month, end: Month | None, words: Words | None = None) -> str:
    vocabulary = words or Words(DEFAULT_LOCALE)
    finish = _month(end) if end else vocabulary("pdf.experience.present")
    return vocabulary("pdf.experience.period", start=_month(start), end=finish)


def years_words(years: float, locale: Locale = DEFAULT_LOCALE) -> str:
    return Words(locale).half_years(years)
