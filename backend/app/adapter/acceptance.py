"""Модели принятия — реализации порта `AcceptanceModel` (mechanics.md, §13)."""

from collections.abc import Sequence

from app.domain.selection import AcceptanceFeatures


class NoAcceptanceModel:
    """Модель ещё не обучена: P(принятия) не считается — множитель 1, в выдаче `null`, а не
    выдуманные 100 %."""

    def predict(self, features: Sequence[AcceptanceFeatures]) -> list[float | None]:
        return [None] * len(features)
