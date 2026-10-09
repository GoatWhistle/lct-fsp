"""Модели принятия — реализации порта `AcceptanceModel` (mechanics.md, §13)."""

from collections.abc import Sequence
from pathlib import Path

from app.domain.selection import AcceptanceFeatures
from app.usecase.interface import AcceptanceModel


class NoAcceptanceModel:
    """Файла модели нет: P(принятия) не считается — множитель 1, в выдаче `null`, а не
    выдуманные 100 %. Модель из файла — `app.adapter.acceptance_catboost`."""

    def predict(self, features: Sequence[AcceptanceFeatures]) -> list[float | None]:
        return [None] * len(features)


def acceptance_model(path: Path) -> AcceptanceModel:
    """Модель CatBoost из файла `path`; файла нет — заглушка, множитель 1. CatBoost с его
    зависимостями импортируется, только когда файл есть."""
    if not path.is_file():
        return NoAcceptanceModel()
    from app.adapter.acceptance_catboost import CatBoostAcceptanceModel

    return CatBoostAcceptanceModel.load(path)
