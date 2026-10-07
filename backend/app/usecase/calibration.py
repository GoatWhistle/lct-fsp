"""Калибровка семейств после ответа кандидата (mechanics.md, §7): шаг Эло, после остановки
попытки — пересчёт связки шкалы и пакетная переоценка.

Идёт отдельно от сценария ответа, в своей единице работы: ответ уже зафиксирован, и сбой
калибровки его не отменяет. Поэтому следующий выбор задания может видеть сложность на один шаг
Эло старше. Алгоритм — за портом `Calibration`, его реализацию сценарий не видит.
"""

from app.domain.attempt import Answer
from app.usecase.interface import Calibration, UnitOfWork


class AnswerCalibration:
    def __init__(self, uow: UnitOfWork, calibration: Calibration) -> None:
        self._uow = uow
        self._calibration = calibration

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
            if answer.stopped:
                self._calibration.relink(specialization, answer.answered_at)
                self._calibration.refit_due(answer.families, specialization, answer.answered_at)
