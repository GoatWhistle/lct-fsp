"""Стандартизированный PDF-профиль кандидата: у всех один вид и один порядок разделов.

Сначала — что подтвердил тест платформы (категория и профиль навыков), затем — что кандидат
сказал о себе сам: читатель сразу видит уровни доверия (mechanics.md, §11). Ожидаемой зарплаты
в PDF нет: файл может оказаться у работодателя, а ожидание ему не показывается (§13).

Шрифт PT Sans лежит рядом под лицензией OFL — кириллица не зависит от шрифтов системы. Глифов
θ и стрелок в нём нет, поэтому уровни подписаны словами.
"""

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fpdf.fonts import FontFace

from app.assessment.schemas import CategoryOut, LevelBandOut, LevelOut, SkillProfileOut
from app.domain.work import WorkFormat
from app.profile.models import CandidateProfile

FONTS = Path(__file__).with_name("fonts")
FONT = "PTSans"
PLATFORM = "Подбор ИТ-специалистов ФСП"
# Москва живёт без перехода на летнее время; tzdata в образе не нужна.
MOSCOW = timezone(timedelta(hours=3), "MSK")

Color = tuple[int, int, int]
TEXT: Color = (20, 23, 31)
MUTED: Color = (93, 100, 117)
BORDER: Color = (221, 225, 234)
ACCENT: Color = (29, 78, 216)

MONTHS = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)
WORK_FORMATS = {
    WorkFormat.office: "офис",
    WorkFormat.hybrid: "гибрид",
    WorkFormat.remote: "удалённо",
}


def render_profile(
    profile: CandidateProfile,
    category: CategoryOut | None,
    skills: SkillProfileOut | None,
    *,
    confidence: float,
    now: datetime,
) -> bytes:
    pdf = _Document(f"{PLATFORM} · профиль сформирован {date_words(now)}")
    pdf.set_title(f"Профиль кандидата — {profile.full_name}")
    pdf.set_author(profile.full_name)
    pdf.set_creator(PLATFORM)
    pdf.set_lang("ru")
    pdf.set_creation_date(now)
    pdf.add_page()

    _header(pdf, profile)
    _verified(pdf, category, skills, confidence)
    _self_reported(pdf, profile)
    return bytes(pdf.output())


class _Document(FPDF):
    def __init__(self, footer_text: str) -> None:
        super().__init__(format="A4")
        self.footer_text = footer_text
        self.add_font(FONT, "", FONTS / "PTSans-Regular.ttf")
        self.add_font(FONT, "B", FONTS / "PTSans-Bold.ttf")
        self.set_margins(18, 16, 18)
        self.set_auto_page_break(auto=True, margin=20)

    def footer(self) -> None:
        self.set_y(-14)
        self.set_draw_color(*BORDER)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.set_font(FONT, size=8)
        self.set_text_color(*MUTED)
        self.cell(self.epw * 0.8, 6, self.footer_text)
        self.cell(0, 6, f"стр. {self.page_no()} из {{nb}}", align="R")


def _header(pdf: _Document, profile: CandidateProfile) -> None:
    _text(pdf, "ПРОФИЛЬ КАНДИДАТА", size=9, style="B", color=ACCENT, height=5)
    _text(pdf, profile.full_name, size=22, style="B", height=10)
    if profile.job_roles:
        _text(pdf, " · ".join(profile.job_roles), size=12, color=MUTED, height=6)
    contacts = [profile.contact_email, profile.contact_phone]
    if profile.telegram:
        contacts.append(f"Telegram @{profile.telegram}")
    pdf.ln(1)
    _text(pdf, " · ".join(c for c in contacts if c), size=10, height=5)


def _verified(
    pdf: _Document,
    category: CategoryOut | None,
    skills: SkillProfileOut | None,
    confidence: float,
) -> None:
    _section(pdf, "Подтверждено тестом платформы")
    if category is None:
        _text(pdf, "Категория пока не присвоена: тест не пройден или ещё идёт.", size=11)
    else:
        _text(pdf, "Категория", size=9, color=MUTED, height=4.5)
        _text(
            pdf,
            f"{category.specialization.name} · {category.grade.name}",
            size=16,
            style="B",
            color=ACCENT,
            height=8,
        )
        _text(
            pdf,
            f"Присвоена {date_words(category.assigned_at)} по адаптивному тесту",
            size=9,
            color=MUTED,
            height=4.5,
        )
    if skills is None:
        return

    pdf.ln(4)
    _text(pdf, "Профиль навыков", size=9, color=MUTED, height=4.5)
    _text(
        pdf,
        f"Общий уровень — {level_words(skills.overall.band)} ({theta_with_error(skills.overall)})",
        size=11,
        height=6,
    )
    pdf.ln(1)
    pdf.set_font(FONT, size=10)
    pdf.set_text_color(*TEXT)
    pdf.set_draw_color(*BORDER)
    with pdf.table(
        col_widths=(50, 32, 18),
        text_align=("LEFT", "LEFT", "RIGHT"),
        borders_layout="HORIZONTAL_LINES",
        headings_style=FontFace(emphasis="BOLD", color=MUTED, size_pt=9),
        line_height=5.5,
        padding=(1.2, 0),
    ) as table:
        table.row(("Тема", "Уровень", "Оценка"))
        for row in skills.topics:
            table.row((row.topic.name, level_words(row.level.band), theta_with_error(row.level)))
    pdf.ln(2)
    _text(
        pdf,
        "Оценка — уровень на общей шкале грейдов, ± — погрешность: чем она меньше, тем увереннее "
        "оценка. «Уверенно middle» — уровень в полосе middle с вероятностью не ниже "
        f"{round(confidence * 100)} %; «между middle и senior» — в одной из двух соседних полос, "
        "уверенности для одной пока не хватает.",
        size=8.5,
        color=MUTED,
        height=4,
    )


def _self_reported(pdf: _Document, profile: CandidateProfile) -> None:
    _section(pdf, "Со слов кандидата")
    rows = [
        ("Стек", ", ".join(t.name for t in profile.stack)),
        ("Стаж в ИТ", experience_words(profile.experience_years)),
        ("Софт-скиллы", ", ".join(profile.soft_skills)),
        ("Формат работы", formats_words(profile.work_formats)),
        ("Город", _city_words(profile)),
        ("Интересные сферы", ", ".join(i.name for i in profile.industries)),
    ]
    _facts(pdf, [(label, value) for label, value in rows if value])
    if profile.about:
        pdf.ln(3)
        _text(pdf, "О себе", size=9, style="B", color=MUTED, height=5)
        _text(pdf, profile.about, size=10, height=5)


def _city_words(profile: CandidateProfile) -> str:
    if profile.city is None:
        return ""
    relocation = "готов к переезду" if profile.relocation else "без переезда"
    return f"{profile.city}, {relocation}"


def _facts(pdf: _Document, rows: Sequence[tuple[str, str]]) -> None:
    pdf.set_font(FONT, size=10)
    pdf.set_text_color(*TEXT)
    with pdf.table(
        col_widths=(22, 78),
        text_align="LEFT",
        v_align="TOP",
        borders_layout="NONE",
        first_row_as_headings=False,
        line_height=5,
        padding=(1, 0),
    ) as table:
        for label, value in rows:
            row = table.row()
            row.cell(label, style=FontFace(color=MUTED))
            row.cell(value)


def _section(pdf: _Document, title: str) -> None:
    pdf.ln(6)
    _text(pdf, title.upper(), size=9, style="B", color=ACCENT, height=5)
    pdf.set_draw_color(*BORDER)
    pdf.line(pdf.l_margin, pdf.get_y() + 0.5, pdf.w - pdf.r_margin, pdf.get_y() + 0.5)
    pdf.ln(3)


def _text(
    pdf: _Document,
    text: str,
    *,
    size: float,
    style: str = "",
    color: Color = TEXT,
    height: float = 5.5,
) -> None:
    pdf.set_font(FONT, style, size)
    pdf.set_text_color(*color)
    pdf.multi_cell(0, height, text, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)


# Слова — те же, что в интерфейсе кандидата (frontend/src/candidate/words.ts).


def level_words(band: LevelBandOut) -> str:
    low, high = band.low, band.high
    if band.confident:
        return f"уверенно {_grade_word(low)}" if low else "ниже стажёра"
    if not low:
        return "стажёр или ниже"
    return f"между {_WITH_WHOM.get(low, low)} и {_grade_word(high or '')}"


_NAMED = {"intern": "стажёр"}
_WITH_WHOM = {"intern": "стажёром"}


def _grade_word(grade: str) -> str:
    return _NAMED.get(grade, grade)


def theta_with_error(level: LevelOut) -> str:
    return f"{_number(level.theta)} ± {_number(level.theta_sd)}"


def _number(value: float) -> str:
    # + 0.0 убирает «−0,0» у маленьких отрицательных.
    return f"{round(value, 1) + 0.0:.1f}".replace(".", ",").replace("-", "−")


def date_words(moment: datetime) -> str:
    day = moment.astimezone(MOSCOW)
    return f"{day.day} {MONTHS[day.month - 1]} {day.year}"


def experience_words(years: int) -> str:
    if years == 0:
        return "меньше года"
    if years % 10 == 1 and years % 100 != 11:
        word = "год"
    elif 2 <= years % 10 <= 4 and not 12 <= years % 100 <= 14:
        word = "года"
    else:
        word = "лет"
    return f"{years} {word}"


def formats_words(formats: Sequence[str]) -> str:
    words = ", ".join(WORK_FORMATS[WorkFormat(f)] for f in formats)
    return words[:1].upper() + words[1:]
