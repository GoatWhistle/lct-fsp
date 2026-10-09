"""Сценарий разбора резюме из PDF и подсказки грейда (mechanics.md, §16;
docs/adr/0002-text-understanding-port.md).

PDF → видимый текст (`ResumeText`, скрытое вырезано) → очистка невидимых знаков → черновик анкеты
(`TextUnderstanding.resume`) → проверка по справочнику. Ни исходный файл, ни черновик не
сохраняются: в профиль черновик попадает только формой профиля, которую кандидат проверил и
сохранил, — тем же сценарием, что ручное заполнение.

Подсказка грейда на шаге выбора грейда считается по сохранённому профилю — стажу и ролям,
которые кандидат подтвердил. Грейд она не выбирает и на категорию не влияет.
"""

import uuid

from app.domain.catalog import Catalog
from app.domain.errors import ResumeTooLarge
from app.domain.experience import ExperienceLimits
from app.domain.need_draft import cleaned
from app.domain.resume_draft import (
    EMPTY_RESUME,
    CheckedResumeDraft,
    GradeHint,
    GradeHintRule,
    ResumeDraft,
    checked_resume,
    grade_hint,
)
from app.usecase.interface import (
    CandidateRepository,
    CatalogRepository,
    Clock,
    ResumeText,
    TextUnderstanding,
    UnitOfWork,
)


class ResumeDrafts:
    def __init__(
        self,
        uow: UnitOfWork,
        catalog: CatalogRepository,
        candidates: CandidateRepository,
        resume_text: ResumeText,
        understanding: TextUnderstanding,
        clock: Clock,
        *,
        rule: GradeHintRule,
        max_bytes: int,
        confident: float,
        experience_limits: ExperienceLimits,
    ) -> None:
        self._uow = uow
        self._catalog = catalog
        self._candidates = candidates
        self._resume_text = resume_text
        self._understanding = understanding
        self._clock = clock
        self._rule = rule
        self._max_bytes = max_bytes
        self._confident = confident
        self._experience_limits = experience_limits

    def parse(self, pdf: bytes) -> CheckedResumeDraft:
        """Черновик анкеты в пределах справочника. Ответ адаптера не того типа — пустой
        черновик: разбор не роняет экран, кандидат заполнит поля сам."""
        if len(pdf) > self._max_bytes:
            raise ResumeTooLarge()
        text = cleaned(self._resume_text.visible_text(pdf))
        with self._uow:
            catalog = Catalog(
                grades=tuple(self._catalog.grades()),
                industries=tuple(self._catalog.industries()),
                specializations=tuple(self._catalog.specializations()),
                technologies=tuple(self._catalog.technologies()),
            )
        today = self._clock.now().date()
        result = self._understanding.resume(text, catalog, today)
        if not isinstance(result, ResumeDraft):
            result = EMPTY_RESUME
        return checked_resume(
            result,
            catalog,
            confident=self._confident,
            rule=self._rule,
            today=today,
            experience_limits=self._experience_limits,
        )

    def grade_hint(self, candidate_id: uuid.UUID) -> GradeHint | None:
        """Подсказка по сохранённому профилю; профиля нет — подсказки нет. Карточка опыта в неё
        не входит: подсказка — по стажу и ролям."""
        with self._uow:
            profile = self._candidates.get(candidate_id).profile
            grades = tuple(self._catalog.grades())
        if profile is None:
            return None
        return grade_hint(
            profile.self_reported.experience_years,
            profile.disclosed.job_roles,
            grades,
            self._rule,
        )
