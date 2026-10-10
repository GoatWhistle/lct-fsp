"""Калибровка семейств — реализация порта `Calibration` (mechanics.md, §7): Эло после каждого
ответа, связка шкалы по якорям и пакетная переоценка. Формулы — `app.domain.calibration`,
состояние хранит порт `CalibrationRepository`; числа конфига механик приходят через конструктор
под своими именами из `docs/parameters.md`.
"""

import logging
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime

from app.domain import bank
from app.domain.calibration import (
    AnchorAnswer,
    CalibratedFamily,
    ExpertGap,
    Link,
    Parameters,
    Response,
    ceiling_gain,
    ceilings,
    elo_update,
    expert_gap,
    fit_link,
    item_fit_rmsd,
    refit,
)
from app.domain.skill import Normal
from app.usecase.interface import CalibrationRepository

log = logging.getLogger(__name__)
# Поля записи журнала о семействе с плохим согласием — задачи банку на ручную проверку.
ITEM_FIT_FAMILY = "item_fit_family"
ITEM_FIT_REASON = "item_fit_reason"


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
        item_fit_groups: int,
        item_fit_rmsd_max: float,
        item_fit_discrimination_min: float,
        item_fit_ceiling_gain_max: float,
        item_fit_ceiling_min: float,
        item_fit_ceiling_step: float,
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
        self.item_fit_groups = item_fit_groups
        self.item_fit_rmsd_max = item_fit_rmsd_max
        self.item_fit_discrimination_min = item_fit_discrimination_min
        self.item_fit_ceiling_gain_max = item_fit_ceiling_gain_max
        self.item_fit_ceiling_min = item_fit_ceiling_min
        self.item_fit_ceiling_step = item_fit_ceiling_step
        # Экспертные параметры по грейду: неизменяемы, считаются один раз.
        self._experts: dict[str, Parameters] = {}

    def expert(self, grade: str) -> Parameters:
        """Стартовые параметры семейства по грейду эксперта: середина полосы и общая a₀ (§2)."""
        found = self._experts.get(grade)
        if found is None:
            found = Parameters(self.expert_discrimination, self.expert_difficulty_by_grade[grade])
            self._experts[grade] = found
        return found

    def current(self, families: Sequence[bank.Family]) -> dict[str, Parameters]:
        """Текущие параметры семейств в выдаче; до первого ответа — экспертные."""
        rows = self._repository.parameters([f.code for f in families])
        result = {}
        for family in families:
            row = rows.get(family.code)
            if row is None:
                result[family.code] = self.expert(family.grade)
            # То же, что `row.issued` и `row.parameters`, без двух свойств на семейство: путь
            # кандидата спрашивает текущие параметры на каждом задании.
            elif row.in_rotation and row.compromised_at is None:
                result[family.code] = Parameters(row.discrimination, row.difficulty)
        return result

    def compromised(self, codes: Iterable[str]) -> set[str]:
        """Семейства из `codes`, которые детектор дрейфа пометил скомпрометированными."""
        rows = self._repository.parameters(list(codes))
        return {code for code, row in rows.items() if row.is_compromised}

    def lock(self, codes: Iterable[str]) -> None:
        """Блокировка строк семейств до конца единицы работы — по порядку кодов: так транзакции,
        которые берут несколько семейств, не ждут друг друга по кругу.

        Вместе с ними — якоря их специализаций: пересчёт связки может вывести якорь из выдачи, и
        его строка должна быть взята в том же порядке, а не после строк попытки."""
        wanted = set(codes)
        specializations = {_specialization(bank.get_family(code)) for code in wanted}
        wanted |= {f.code for f in bank.BANK if f.anchor and _specialization(f) in specializations}
        for code in sorted(wanted):
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
        """Пересчёт связок шкалы по ответам на якорные семейства в выдаче из окна связки —
        последних `calibration_link_window_attempts` остановленных попыток по специализации (§7).

        Заодно — согласие якорей с моделью: якорь, набравший в окне
        `calibration_refit_min_responses` ответов с итоговой оценкой, сверяется на своих
        фиксированных (a, b) с уровнями, переведёнными новой связкой. Якорь с плохим согласием
        гнёт связку, по которой судят остальных, поэтому выводится по одному — худший, — и связка
        пересчитывается без его ответов, пока плохих не останется.
        """
        anchors = [f.code for f in bank.BANK if f.anchor]
        rows = self._repository.parameters(anchors)
        answers = self._repository.anchor_answers(
            specialization,
            [code for code in anchors if code not in rows or rows[code].issued],
            self.calibration_link_window_attempts,
        )
        while True:
            before, rest = self._links(answers)
            worst = self._worst_anchor(answers, rest)
            if worst is None:
                break
            code, rmsd = worst
            self._retire_misfit(code, rmsd)
            answers = [a for a in answers if a.family_code != code]
        self._repository.save_links(specialization, before, rest, now)

    def refit_due(self, codes: Iterable[str], specialization: str, now: datetime) -> None:
        """Пакетная переоценка семейств, набравших `calibration_refit_min_responses` ответов с
        итоговыми оценками кандидатов. Строки семейств блокируются по порядку кодов и держатся
        до конца единицы работы калибровки — она идёт после фиксации ответа.

        Уровни кандидатов переводятся связкой шкалы. Результат — новые текущие и опорные
        параметры. Опорная сложность легче экспертной больше допустимого — семейство уходит из
        выдачи до ручной проверки; тяжелее — остаётся в выдаче с пометкой (`expert_gaps`).
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
            gap = expert_gap(fitted, start, gap=self.calibration_expert_gap_review)
            # Дрейф и согласие проверяются независимо: вывод — по любой из проверок.
            if self._misfits(code, responses, start, fitted):
                row.in_rotation = False
            if gap == ExpertGap.EASIER:
                row.in_rotation = False
                log.warning(
                    "Семейство %s легче экспертной оценки: b = %.2f при экспертной %.2f — "
                    "выведено из выдачи до ручной проверки",
                    code,
                    fitted.difficulty,
                    start.difficulty,
                )
            elif gap == ExpertGap.HARDER:
                log.warning(
                    "Семейство %s тяжелее экспертной оценки: b = %.2f при экспертной %.2f — "
                    "остаётся в выдаче, помечено в отчёте покрытия",
                    code,
                    fitted.difficulty,
                    start.difficulty,
                )
            self._repository.save(row)

    def expert_gaps(self, families: Sequence[bank.Family]) -> dict[str, ExpertGap]:
        """Семейства, чья опорная сложность разошлась с экспертной больше
        `calibration_expert_gap_review`, — в обе стороны. Пометка выводится из опорных
        параметров, отдельно не хранится; до переоценки сверять не с чем."""
        rows = self._repository.parameters([f.code for f in families])
        result = {}
        for family in families:
            row = rows.get(family.code)
            if row is None or row.reference is None:
                continue
            gap = expert_gap(
                row.reference, self.expert(family.grade), gap=self.calibration_expert_gap_review
            )
            if gap is not None:
                result[family.code] = gap
        return result

    def _links(self, answers: Sequence[AnchorAnswer]) -> tuple[Link, Link]:
        """Связки по оценкам до ответа и без ответа; ответов меньше
        `calibration_refit_min_responses` — тождественные."""
        minimum = self.calibration_refit_min_responses
        return (
            fit_link([(a.params, a.before) for a in answers], min_responses=minimum),
            fit_link(
                [(a.params, a.rest) for a in answers if a.rest is not None],
                min_responses=minimum,
            ),
        )

    def _worst_anchor(
        self, answers: Sequence[AnchorAnswer], link: Link
    ) -> tuple[str, float] | None:
        """Якорь с худшим согласием выше `item_fit_rmsd_max` среди набравших
        `calibration_refit_min_responses` ответов; уровни переводятся связкой `link`."""
        by_anchor: dict[str, list[AnchorAnswer]] = defaultdict(list)
        for a in answers:
            by_anchor[a.family_code].append(a)
        worst = None
        for code, group in sorted(by_anchor.items()):
            responses = [
                Response(link.apply(a.rest.level), a.rest.correct) for a in group if a.rest
            ]
            if len(responses) < self.calibration_refit_min_responses:
                continue
            rmsd = item_fit_rmsd(responses, group[0].params, groups=self.item_fit_groups)
            if rmsd > self.item_fit_rmsd_max and (worst is None or rmsd > worst[1]):
                worst = (code, rmsd)
        return worst

    def _misfits(
        self,
        code: str,
        responses: Sequence[Response],
        start: Parameters,
        fitted: Parameters,
    ) -> bool:
        """Согласие семейства с 2PL после переоценки: переоценённая разделяющая сила ниже
        `item_fit_discrimination_min` или модель с потолком объясняет ответы лучше 2PL больше чем
        на `item_fit_ceiling_gain_max` нат (§7)."""
        if fitted.discrimination < self.item_fit_discrimination_min:
            self._report_misfit(
                code,
                f"â = {fitted.discrimination:.2f} при допустимой не ниже "
                f"{self.item_fit_discrimination_min:.2f}",
            )
            return True
        gain = ceiling_gain(
            responses,
            start,
            fitted,
            ceilings=ceilings(self.item_fit_ceiling_min, self.item_fit_ceiling_step),
            difficulty_prior_sd=self.calibration_refit_difficulty_prior_sd,
            log_discrimination_prior_sd=self.calibration_refit_log_discrimination_prior_sd,
        )
        if gain <= self.item_fit_ceiling_gain_max:
            return False
        self._report_misfit(
            code,
            f"модель с потолком лучше 2PL на {gain:.2f} нат при допустимых "
            f"{self.item_fit_ceiling_gain_max:.2f}",
        )
        return True

    def _retire_misfit(self, code: str, rmsd: float) -> None:
        row = self._locked(bank.get_family(code))
        row.in_rotation = False
        self._repository.save(row)
        self._report_misfit(code, f"RMSD = {rmsd:.3f} при допустимом {self.item_fit_rmsd_max:.3f}")

    def _report_misfit(self, code: str, reason: str) -> None:
        """Задача банку на ручную проверку — запись в журнал с кодом семейства и причиной."""
        log.warning(
            "Семейство %s не согласуется с моделью: %s — выведено из выдачи до ручной проверки",
            code,
            reason,
            extra={ITEM_FIT_FAMILY: code, ITEM_FIT_REASON: reason},
        )

    def _locked(self, family: bank.Family) -> CalibratedFamily:
        return self._repository.locked(family.code, self.expert(family.grade))


def _specialization(family: bank.Family) -> str:
    """Специализация семейства — первая часть кода темы: `<специализация>.<тема>`."""
    return family.topic.split(".", 1)[0]
