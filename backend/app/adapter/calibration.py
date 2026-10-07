"""Калибровка семейств — реализация порта `Calibration` (mechanics.md, §7): Эло после каждого
ответа, связка шкалы по якорям и пакетная переоценка. Формулы — `app.domain.calibration`,
состояние хранит порт `CalibrationRepository`; числа конфига механик приходят через конструктор
под своими именами из `docs/parameters.md`.
"""

import logging
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime

from app.domain import bank
from app.domain.calibration import (
    CalibratedFamily,
    Parameters,
    Response,
    elo_update,
    fit_link,
    needs_review,
    refit,
)
from app.domain.skill import Normal
from app.usecase.interface import CalibrationRepository

log = logging.getLogger(__name__)


class EloCalibration:
    def __init__(
        self,
        repository: CalibrationRepository,
        *,
        expert_discrimination: float,
        expert_difficulty_by_grade: Mapping[str, float],
        elo_k_initial: float,
        elo_k_half_responses: int,
        elo_k_min: float,
        calibration_refit_min_responses: int,
        calibration_expert_gap_review: float,
        calibration_refit_difficulty_prior_sd: float,
        calibration_refit_log_discrimination_prior_sd: float,
        calibration_link_window_attempts: int,
    ) -> None:
        self._repository = repository
        self.expert_discrimination = expert_discrimination
        self.expert_difficulty_by_grade = dict(expert_difficulty_by_grade)
        self.elo_k_initial = elo_k_initial
        self.elo_k_half_responses = elo_k_half_responses
        self.elo_k_min = elo_k_min
        self.calibration_refit_min_responses = calibration_refit_min_responses
        self.calibration_expert_gap_review = calibration_expert_gap_review
        self.calibration_refit_difficulty_prior_sd = calibration_refit_difficulty_prior_sd
        self.calibration_refit_log_discrimination_prior_sd = (
            calibration_refit_log_discrimination_prior_sd
        )
        self.calibration_link_window_attempts = calibration_link_window_attempts

    def expert(self, grade: str) -> Parameters:
        """Стартовые параметры семейства по грейду эксперта: середина полосы и общая a₀ (§2)."""
        return Parameters(self.expert_discrimination, self.expert_difficulty_by_grade[grade])

    def current(self, families: Sequence[bank.Family]) -> dict[str, Parameters]:
        """Текущие параметры семейств в выдаче; до первого ответа — экспертные."""
        rows = self._repository.parameters([f.code for f in families])
        result = {}
        for family in families:
            row = rows.get(family.code)
            if row is None:
                result[family.code] = self.expert(family.grade)
            elif row.in_rotation:
                result[family.code] = row.parameters
        return result

    def lock(self, codes: Iterable[str]) -> None:
        """Блокировка строк семейств до конца единицы работы — по порядку кодов: так транзакции,
        которые берут несколько семейств, не ждут друг друга по кругу."""
        for code in sorted(set(codes)):
            self._locked(bank.get_family(code))

    def learn(
        self, specialization: str, family_code: str, level_before: Normal, correct: bool
    ) -> None:
        """Эло после ответа: сложность семейства сдвигается по неожиданности ответа (§7).

        Строка семейства блокируется до конца единицы работы: два ответа на одно семейство не
        затирают шаги друг друга. У якорного и у переоценённого семейства растёт только счётчик
        ответов: после пакетной переоценки текущие параметры — опорные.
        """
        family = bank.get_family(family_code)
        row = self._locked(family)
        if not family.anchor and row.refitted_at is None:
            link = self._repository.links(specialization)[0]
            updated = elo_update(
                row.parameters,
                Response(link.apply(level_before), correct),
                row.responses,
                k_initial=self.elo_k_initial,
                k_half_responses=self.elo_k_half_responses,
                k_min=self.elo_k_min,
            )
            row.difficulty = updated.difficulty
        row.responses += 1
        self._repository.save(row)

    def relink(self, specialization: str, now: datetime) -> None:
        """Пересчёт связок шкалы по ответам на якорные семейства из последних
        `calibration_link_window_attempts` попыток по специализации (§7)."""
        anchors = [f.code for f in bank.BANK if f.anchor]
        answers = self._repository.anchor_answers(
            specialization, anchors, self.calibration_link_window_attempts
        )
        before = [(a.params, a.before) for a in answers]
        rest = [(a.params, a.rest) for a in answers if a.rest is not None]
        minimum = self.calibration_refit_min_responses
        self._repository.save_links(
            specialization,
            fit_link(before, min_responses=minimum),
            fit_link(rest, min_responses=minimum),
            now,
        )

    def refit_due(self, codes: Iterable[str], specialization: str, now: datetime) -> None:
        """Пакетная переоценка семейств, набравших `calibration_refit_min_responses` ответов с
        итоговыми оценками кандидатов. Строки семейств блокируются по порядку кодов и держатся
        до конца единицы работы ответа.

        Уровни кандидатов переводятся связкой шкалы. Результат — новые текущие и опорные
        параметры. Опорная сложность легче экспертной больше допустимого — семейство уходит из
        выдачи до ручной проверки.
        """
        link = self._repository.links(specialization)[1]
        for code in sorted(set(codes)):
            family = bank.get_family(code)
            if family.anchor or (
                self._repository.ready_responses(code) < self.calibration_refit_min_responses
            ):
                continue
            row = self._locked(family)
            if row.refitted_at is not None:
                continue
            start = self.expert(family.grade)
            responses = [
                Response(link.apply(r.level), r.correct)
                for r in self._repository.rest_answers(code)
            ]
            fitted = refit(
                responses,
                start,
                difficulty_prior_sd=self.calibration_refit_difficulty_prior_sd,
                log_discrimination_prior_sd=self.calibration_refit_log_discrimination_prior_sd,
            )
            row.discrimination, row.difficulty = fitted.discrimination, fitted.difficulty
            row.reference = fitted
            row.refitted_at = now
            if needs_review(fitted, start, expert_gap=self.calibration_expert_gap_review):
                row.in_rotation = False
                log.warning(
                    "Семейство %s легче экспертной оценки: b = %.2f при экспертной %.2f — "
                    "выведено из выдачи до ручной проверки",
                    code,
                    fitted.difficulty,
                    start.difficulty,
                )
            self._repository.save(row)

    def _locked(self, family: bank.Family) -> CalibratedFamily:
        return self._repository.locked(family.code, self.expert(family.grade))
