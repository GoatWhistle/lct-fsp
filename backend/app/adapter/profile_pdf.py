from collections.abc import Sequence
from datetime import datetime, timedelta, timezone

from app.adapter.brand.pdf_kit import (
    MONO,
    UI,
    BrandDocument,
    level_words,
    pill,
    pills,
    ruler,
    section,
    terms,
    text,
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
        _hero(doc, disclosed)
        _verified(doc, sheet.category, sheet.skill_profile, sheet.grade_confidence)
        _fsp(doc, sheet.fsp_achievements)
        _self_reported(doc, sheet.self_reported, disclosed)
        _experience(doc, disclosed.experience, sheet.technology_years)
        return bytes(doc.output())


def _caption(doc: BrandDocument, value: str) -> None:
    text(doc, value, size=7.5, mono=True, tone=doc.ink.tertiary, height=4)


def _hero(doc: BrandDocument, disclosed: Disclosed) -> None:
    words = doc.words
    text(doc, disclosed.full_name, size=22, bold=True, height=10)
    if disclosed.job_roles:
        doc.ln(1.5)
        pills(doc, disclosed.job_roles, fill=doc.ink.tint, tone=doc.ink.accent)
    telegram = f"@{disclosed.telegram}" if disclosed.telegram else ""
    contacts = [
        (words("pdf.contacts.email"), disclosed.contact_email),
        (words("pdf.contacts.phone"), disclosed.contact_phone or ""),
        (words("pdf.contacts.telegram"), telegram),
    ]
    shown = [(label, value) for label, value in contacts if value]
    doc.ln(2)
    y = doc.get_y()
    column = doc.epw / max(len(shown), 1)
    for index, (label, value) in enumerate(shown):
        x = doc.l_margin + index * column
        doc.set_xy(x, y)
        doc.set_font(MONO, "", 7.5)
        doc.set_text_color(*doc.ink.tertiary)
        doc.cell(column, 4, label)
        doc.set_xy(x, y + 4.5)
        doc.set_font(UI, "", 10)
        doc.set_text_color(*doc.ink.text)
        doc.cell(column, 5, value)
    doc.set_y(y + 11)


def _verified(
    doc: BrandDocument,
    category: Category | None,
    skills: SkillProfile | None,
    confidence: float,
) -> None:
    words = doc.words
    section(doc, words("pdf.sections.verified"))
    if category is None:
        text(doc, words("pdf.category.none"), size=10.5, height=5.5)
    else:
        _category(doc, category)
    if skills is None:
        return
    doc.ln(4)
    _caption(doc, words("pdf.skills.overall"))
    overall = skills.overall
    caption = f"{level_words(words, overall.band)}, {uncertainty_words(words, overall.theta_sd)}"
    text(doc, caption, size=10.5, bold=True, height=6)
    doc.set_y(ruler(doc, overall, doc.l_margin, doc.get_y() + 2, doc.epw, labels=True) + 3)
    _caption(doc, words("pdf.skills.label"))
    doc.ln(1)
    for row in skills.topics:
        _topic(doc, row)
    doc.ln(2)
    note = words("pdf.skills.note", confidence=round(confidence * 100))
    text(doc, note, size=8, tone=doc.ink.tertiary, height=4)


def _category(doc: BrandDocument, category: Category) -> None:
    words = doc.words
    _caption(doc, words("pdf.category.label"))
    doc.set_xy(doc.l_margin, doc.get_y() + 0.5)
    specialization = words.catalog("specialization", category.specialization)
    doc.set_font(MONO, "B", 17)
    doc.set_text_color(*doc.ink.text)
    doc.cell(doc.get_string_width(specialization) + 4, 9, specialization)
    doc.set_text_color(*doc.ink.accent)
    doc.cell(0, 9, words.catalog("grade", category.grade), new_x="LMARGIN", new_y="NEXT")
    day = words.date(category.assigned_at.astimezone(MOSCOW).date())
    text(doc, words("pdf.category.assigned", date=day), size=8.5, tone=doc.ink.secondary)


def _topic(doc: BrandDocument, row: TopicLevel) -> None:
    if doc.get_y() > doc.h - 34:
        doc.add_page()
    y = doc.get_y()
    doc.set_draw_color(*doc.ink.hairline)
    doc.set_line_width(0.2)
    doc.line(doc.l_margin, y, doc.w - doc.r_margin, y)
    doc.set_xy(doc.l_margin, y + 1.6)
    doc.set_font(UI, "", 9.5)
    doc.set_text_color(*doc.ink.text)
    doc.multi_cell(TOPIC_COLUMN - 4, 4.6, doc.words.catalog("topic", row.topic))
    doc.set_x(doc.l_margin)
    doc.set_font(MONO, "", 7.5)
    doc.set_text_color(*doc.ink.secondary)
    doc.multi_cell(TOPIC_COLUMN - 4, 4, level_words(doc.words, row.level.band))
    bottom = doc.get_y()
    ruler(doc, row.level, doc.l_margin + TOPIC_COLUMN, y + 4.2, RULER_WIDTH, labels=False)
    x = doc.l_margin + TOPIC_COLUMN + RULER_WIDTH + 5
    for source in sorted(row.sources):
        tone = doc.ink.fsp if source == "fsp" else doc.ink.accent
        label = doc.words(f"pdf.sources.{source}")
        x += pill(doc, label, x, y + 2.8, fill=doc.ink.tint, tone=tone, size=7.5) + 1.5
    doc.set_y(max(bottom, y + 9) + 1.4)


def _fsp(doc: BrandDocument, achievements: Sequence[ConfirmedAchievement]) -> None:
    words = doc.words
    section(doc, words("pdf.sections.fsp"))
    if not achievements:
        text(doc, words("pdf.fsp.empty"), size=10.5, height=5.5)
        return
    for item in achievements:
        y = doc.get_y()
        result = words.catalog("fspResult", item.result.value)
        width = pill(doc, result, doc.l_margin, y, fill=doc.ink.tint, tone=doc.ink.fsp)
        doc.set_xy(doc.l_margin + width + 3, y)
        doc.set_font(MONO, "", 8.5)
        doc.set_text_color(*doc.ink.secondary)
        doc.cell(0, 5.4, item.date.strftime("%d.%m.%Y"), new_x="LMARGIN", new_y="NEXT")
        doc.ln(1)
        text(doc, item.event, size=10.5, bold=True, height=5.2)
        details = [words.catalog("discipline", item.discipline)]
        if item.place is not None:
            details.append(words("pdf.fsp.place", place=item.place))
        if item.team_role is not None:
            details.append(words("pdf.fsp.role", role=item.team_role.name))
        text(doc, ", ".join(details), size=9.5, tone=doc.ink.secondary, height=5)
        doc.ln(3)
    text(doc, words("pdf.fsp.note"), size=8, tone=doc.ink.tertiary, height=4)


def _self_reported(doc: BrandDocument, profile: SelfReported, disclosed: Disclosed) -> None:
    words = doc.words
    section(doc, words("pdf.sections.self"))
    formats = ", ".join(words.catalog("workFormat", f.value) for f in profile.work_formats)
    industries = ", ".join(words.catalog("industry", i) for i in profile.industries)
    rows = [
        (words("pdf.self.stack"), ", ".join(t.name for t in profile.stack)),
        (words("pdf.self.experience"), words.years(profile.experience_years)),
        (words("pdf.self.soft"), ", ".join(disclosed.soft_skills)),
        (words("pdf.self.formats"), formats[:1].upper() + formats[1:]),
        (words("pdf.self.city"), _city(words, profile)),
        (words("pdf.self.industries"), industries),
    ]
    terms(doc, [(label, value) for label, value in rows if value])
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
        terms(doc, [(words("pdf.experience.technologyYears"), listed)])
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
