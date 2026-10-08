"""Детектор дрейфа — реализация порта `DriftDetector` (mechanics.md, §8): risk-adjusted
Bernoulli CUSUM по семейству от опорных параметров. Формула — `app.domain.protection`, состояние
— в строке калибровки семейства (`CalibrationRepository`); числа конфига механик приходят через
конструктор под своими именами из `docs/parameters.md`.
"""

import logging
from datetime import datetime

from app.domain import bank
from app.domain.protection import cusum_step
from app.domain.skill import Normal
from app.usecase.interface import CalibrationRepository

log = logging.getLogger(__name__)


class CusumDriftDetector:
    def __init__(
        self, repository: CalibrationRepository, *, drift_shift: float, drift_cusum_h: float
    ) -> None:
        self._repository = repository
        self.drift_shift = drift_shift
        self.drift_cusum_h = drift_cusum_h

    def observe(
        self,
        specialization: str,
        family_code: str,
        level_before: Normal,
        correct: bool,
        at: datetime,
    ) -> bool:
        """Шаг CUSUM по ответу; True — семейство только что помечено скомпрометированным.

        Детектор работает от опорных параметров — после первой пакетной переоценки; у якоря они
        заморожены с самого начала. До этого семейство на разогреве, и шага нет. Уровень
        кандидата переводится связкой шкалы по оценкам до ответа — той же, что у шага Эло.
        Строку семейства держит блокировка калибровки до конца единицы работы.
        """
        family = bank.get_family(family_code)
        row = self._repository.parameters([family_code]).get(family_code)
        if row is None or row.is_compromised:
            return False
        reference = row.parameters if family.anchor else row.reference
        if reference is None:
            return False
        level = self._repository.links(specialization)[0].apply(level_before).mean
        row.drift = cusum_step(row.drift, reference, level, correct, shift=self.drift_shift)
        flagged = row.drift > self.drift_cusum_h
        if flagged:
            row.compromised_at = at
            log.warning(
                "Семейство %s скомпрометировано: CUSUM %.2f выше порога %.2f — выведено из "
                "выдачи, нужна замена",
                family_code,
                row.drift,
                self.drift_cusum_h,
            )
        self._repository.save(row)
        return flagged
