"""Проверка подбора на своём наборе пар «вакансия — кандидат» (docs/sandbox.md).

Набор — JSON: вакансии текстом, кандидаты-персонажи с грейдом и уровнями по темам, пары с
разметкой релевантности 0–3. Персонажи проходят тест в симуляторе стенда с той же моделью
ответов, что у D1, и получают категорию тем же сценарием, что HTTP; вакансии разбираются тем же
разбором текста, подборка строится сценарием подбора. Итог — доля релевантных в топ-k и nDCG@k
по каждой вакансии и в среднем, плюс выдача с соответствием.

Песочница изолирована: стенд свой, в памяти, с реальными данными не соприкасается и после
прогона исчезает вместе с процессом.
"""

import json
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from app.domain.need import NeedForm
from app.domain.need_draft import CheckedDraft
from app.domain.work import WorkFormat
from settings import Mechanics
from validation.main import build_stand
from validation.market import Candidate, Market, warm
from validation.metrics import ndcg_at, precision_at
from validation.simulate import EMPLOYER

TOP_K = 10
WARM_RESPONSES = 100


@dataclass(frozen=True)
class Character:
    id: str
    specialization: str
    grade: str
    levels: dict[str, float]


@dataclass(frozen=True)
class Vacancy:
    id: str
    text: str


@dataclass(frozen=True)
class Pair:
    vacancy: str
    candidate: str
    relevance: int


@dataclass(frozen=True)
class SandboxSet:
    vacancies: tuple[Vacancy, ...]
    candidates: tuple[Character, ...]
    pairs: tuple[Pair, ...]


@dataclass(frozen=True)
class VacancyResult:
    vacancy: str
    parsed: bool
    ranked: tuple[tuple[str, float | None, int], ...]
    precision: float | None
    ndcg: float | None


@dataclass(frozen=True)
class SandboxReport:
    results: tuple[VacancyResult, ...]
    mean_precision: float | None
    mean_ndcg: float | None


def load_set(path: Path) -> SandboxSet:
    data = json.loads(path.read_text(encoding="utf-8"))
    candidates = tuple(Character(**c) for c in data["candidates"])
    ids = {c.id for c in candidates}
    vacancies = tuple(Vacancy(**v) for v in data["vacancies"])
    known = {v.id for v in vacancies}
    pairs = tuple(Pair(**p) for p in data["pairs"])
    for p in pairs:
        if p.candidate not in ids or p.vacancy not in known:
            raise ValueError(f"пара {p.vacancy} — {p.candidate}: нет вакансии или кандидата")
        if not 0 <= p.relevance <= 3:
            raise ValueError(f"релевантность {p.relevance}: нужна 0–3")
    return SandboxSet(vacancies, candidates, pairs)


def _form(draft: CheckedDraft) -> NeedForm | None:
    if draft.specialization is None or draft.grade is None:
        return None
    return NeedForm(
        title=draft.title or "Вакансия",
        team_description="",
        specialization=draft.specialization.code,
        grade=draft.grade.code,
        stack=tuple(t.code for t in draft.stack),
        topic_importance={},
        work_format=draft.work_format or WorkFormat.remote,
        city=draft.city,
        salary_from=draft.salary_from,
        salary_to=draft.salary_to,
    )


def run_set(given: SandboxSet, mechanics: Mechanics, seed: int = 7) -> SandboxReport:
    """Прогон набора на своём стенде: по специализации — банк, прогретый честными кандидатами,
    затем персонажи проходят определение и попадают в пул."""
    stands: dict[str, Market] = {}
    users: dict[str, tuple[str, object]] = {}
    for character in given.candidates:
        market = stands.get(character.specialization)
        if market is None:
            market = warm(Market(character.specialization, mechanics, seed), WARM_RESPONSES)
            stands[character.specialization] = market
        topics = market.prior.topics
        level = {t: character.levels.get(t, 0.0) for t in topics}
        determined = market.determine(Candidate(level, character.grade))
        market.enlist(determined.user, claimed=character.grade)
        users[character.id] = (character.specialization, determined.user)
    relevance = {(p.vacancy, p.candidate): p.relevance for p in given.pairs}
    results = []
    parser = build_stand(mechanics).need_drafts()
    for vacancy in given.vacancies:
        parsed = parser.parse(vacancy.text)
        form = _form(parsed) if isinstance(parsed, CheckedDraft) else None
        if form is None or form.specialization not in stands:
            results.append(VacancyResult(vacancy.id, False, (), None, None))
            continue
        market = stands[form.specialization]
        page = market.stand.selections().build_draft(EMPLOYER, form, limit=len(users) + 1)
        by_user = {u: cid for cid, (_, u) in users.items()}
        ranked = tuple(
            (
                by_user[e.candidate_id],
                e.match_score,
                relevance.get((vacancy.id, by_user[e.candidate_id]), 0),
            )
            for e in page.entries
            if e.candidate_id in by_user
        )
        grades = [r for _, _, r in ranked]
        pool = [r for (v, _), r in relevance.items() if v == vacancy.id]
        results.append(
            VacancyResult(
                vacancy.id,
                True,
                ranked,
                precision_at(grades, TOP_K),
                ndcg_at(grades, pool, TOP_K),
            )
        )
    return SandboxReport(
        tuple(results),
        _mean([r.precision for r in results]),
        _mean([r.ndcg for r in results]),
    )


def _mean(values: Sequence[float | None]) -> float | None:
    known = [v for v in values if v is not None]
    return statistics.fmean(known) if known else None


def render(report: SandboxReport) -> str:
    lines = [
        f"| Вакансия | Разобрана | Доля релевантных в топ-{TOP_K} | nDCG@{TOP_K} |",
        "|---|---|---|---|",
    ]
    for r in report.results:
        precision = "—" if r.precision is None else f"{r.precision:.3f}"
        ndcg = "—" if r.ndcg is None else f"{r.ndcg:.3f}"
        lines.append(f"| {r.vacancy} | {'да' if r.parsed else 'нет'} | {precision} | {ndcg} |")
    mean_p = "—" if report.mean_precision is None else f"{report.mean_precision:.3f}"
    mean_n = "—" if report.mean_ndcg is None else f"{report.mean_ndcg:.3f}"
    lines.append(f"| **в среднем** | | {mean_p} | {mean_n} |")
    for r in report.results:
        if r.ranked:
            lines.append(f"\n**{r.vacancy}** — выдача:\n")
            for place, (cid, score, rel) in enumerate(r.ranked, start=1):
                shown = "—" if score is None else f"{score:.2f}"
                lines.append(f"{place}. {cid}: соответствие {shown}, разметка {rel}")
    return "\n".join(lines)
