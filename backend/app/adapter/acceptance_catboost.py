"""Модель принятия на CatBoost — реализация порта `AcceptanceModel` (mechanics.md, §13).

Признаки — строки `app.domain.acceptance.encode`, монотонные ограничения — `MONOTONE` оттуда же.
Обучает стенд валидации (`python -m validation acceptance`) на решениях синтетических
кандидатов; файл модели лежит в репо, прод его только загружает — `acceptance_model` в
`app.adapter.acceptance`.

Обучение — только на CPU: монотонные ограничения CatBoost есть только там. Сид и число потоков
фиксированы в конфиге механик — повторное обучение на тех же строках даёт ту же модель.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from catboost import CatBoostClassifier, Pool

from app.domain.acceptance import CATEGORICAL, COLUMNS, MONOTONE, Row, encode
from app.domain.selection import AcceptanceFeatures


@dataclass(frozen=True)
class Training:
    """Параметры обучения — `acceptance_model_*` конфига механик."""

    iterations: int
    depth: int
    learning_rate: float
    random_seed: int
    thread_count: int


def _pool(rows: Sequence[Row], labels: Sequence[int] | None = None) -> Pool:
    return Pool(
        [list(r) for r in rows],
        label=list(labels) if labels is not None else None,
        cat_features=[COLUMNS.index(c) for c in CATEGORICAL],
        feature_names=list(COLUMNS),
    )


class CatBoostAcceptanceModel:
    def __init__(self, model: CatBoostClassifier) -> None:
        if list(model.feature_names_) != list(COLUMNS):
            raise ValueError(f"модель принятия на других признаках: {model.feature_names_}")
        self._model = model

    @classmethod
    def load(cls, path: Path) -> "CatBoostAcceptanceModel":
        model = CatBoostClassifier()
        model.load_model(str(path))
        return cls(model)

    def save(self, path: Path) -> None:
        self._model.save_model(str(path))

    def predict(self, features: Sequence[AcceptanceFeatures]) -> list[float | None]:
        """Без вилки — None: P не считается."""
        rows = [encode(f) for f in features]
        known = [r for r in rows if r is not None]
        found = iter(self.predict_rows(known))
        return [None if r is None else next(found) for r in rows]

    def predict_rows(self, rows: Sequence[Row]) -> list[float]:
        if not rows:
            return []
        return [float(p) for p in self._model.predict_proba(_pool(rows))[:, 1]]


def fit(rows: Sequence[Row], labels: Sequence[int], training: Training) -> CatBoostAcceptanceModel:
    """Классификатор на строках `rows` с метками принято — 1, отклонено и истекло — 0."""
    model = CatBoostClassifier(
        iterations=training.iterations,
        depth=training.depth,
        learning_rate=training.learning_rate,
        random_seed=training.random_seed,
        thread_count=training.thread_count,
        task_type="CPU",
        loss_function="Logloss",
        monotone_constraints=dict(MONOTONE),
        allow_writing_files=False,
        verbose=False,
    )
    model.fit(_pool(rows, labels))
    # Время обучения и случайный guid — единственное, чем отличаются файлы двух обучений на тех же
    # строках: без них повторное обучение даёт тот же файл байт в байт.
    metadata = model.get_metadata()
    metadata["train_finish_time"] = ""
    metadata["model_guid"] = f"acceptance-{training.random_seed}"
    return CatBoostAcceptanceModel(model)
