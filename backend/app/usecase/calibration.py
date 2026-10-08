"""Калибровка семейств после ответа кандидата (mechanics.md, §7): шаг Эло, шаг детектора дрейфа
(§8), после остановки попытки — пересчёт связки шкалы и пакетная переоценка.

Идёт отдельно от сценария ответа, в своей единице работы: ответ уже зафиксирован, и сбой
калибровки его не отменяет. Поэтому следующий выбор задания может видеть сложность на один шаг
Эло старше, а семейство, которое детектор только что пометил, — ещё в выдаче. Алгоритмы — за
портами `Calibration` и `DriftDetector`, их реализации сценарий не видит.
"""

from app.domain.attempt import Answer
from app.usecase.interface import Calibration, DriftDetector, UnitOfWork


class AnswerCalibration:
    def __init__(self, uow: UnitOfWork, calibration: Calibration, drift: DriftDetector) -> None:
        self._uow = uow
        self._calibration = calibration
        self._drift = drift

    def calibrate(self, answer: Answer) -> None:
        """Калибровка по ответу из сценария ответа; сбой пробрасывается — что с ним делать,
        решает вызывающий."""
        specialization = answer.specialization_code
        with self._uow:
            if answer.stopped:
                # Переоценка держит строки семейств попытки до конца транзакции. Берём их сразу и
                # по порядку кодов, до шага Эло: иначе две одновременные остановки сцепятся
                # блокировками.
                self._calibration.lock(answer.families)
            self._calibration.learn(
                specialization, answer.family_code, answer.level_before, answer.correct
            )
            self._observe(answer)
            if answer.stopped:
                self._calibration.relink(specialization, answer.answered_at)
                self._calibration.refit_due(answer.families, specialization, answer.answered_at)

    def watch(self, answer: Answer) -> None:
        """Только детектор дрейфа, без калибровки: банк заморожен, а утечку ловить надо — так
        стенд валидации меряет детектор на прогретом банке (M14, M15)."""
        with self._uow:
            self._calibration.lock([answer.family_code])
            self._observe(answer)

    def _observe(self, answer: Answer) -> None:
        self._drift.observe(
            answer.specialization_code,
            answer.family_code,
            answer.level_before,
            answer.correct,
            answer.answered_at,
        )
