"""Модель навыка с кэшем префиксов наблюдений — декоратор над пошаговой моделью.

Путь кандидата оценивает уровень много раз по одному растущему списку ответов: на показ, на
ответ, на остановку и без каждого ответа по очереди. Оценка по префиксу — функция от
`(prior, to_mode, наблюдения префикса)`, поэтому её можно запомнить и продолжить следующими
наблюдениями, а не считать с начала. Шаги — те же, на тех же входах и в том же порядке: оценка
совпадает с расчётом с нуля до бита.

Префиксы — дерево: корень — `(prior, to_mode)`, ребро — наблюдение. Узел хранится записью
`(id родителя, наблюдение) → (id узла, состояние)`: поиск самого длинного посчитанного префикса —
проход от корня по одной записи на наблюдение, без хэширования префиксов целиком.

Память ограничена числом записей, вытесняется давно не использованная (LRU). Проход от корня
трогает весь путь, так что вытесняются старые ветки. Если вытеснен узел внутри ветки, его потомки
недостижимы — id узла новый при пересчёте — и уходят тем же LRU.
"""

import threading
from collections import OrderedDict
from collections.abc import Hashable, Iterable
from datetime import datetime
from typing import Protocol

from app.domain.skill import Observation, Prior, SkillEstimate, SkillProfileLevels

__all__ = ["PROCESS_ENTRIES", "PrefixCachedSkillModel", "Stepwise"]

# Записей на процесс: кэш один, его держит точка сборки. Запись — оценка по префиксу, около 4 КБ
# при 8 темах: 10 000 — около 40 МБ. Попытка теста занимает порядка тысячи записей (префиксы,
# оценки без каждого ответа, профиль): попадания сохраняются для нескольких одновременных
# кандидатов, промах только пересчитывает.
PROCESS_ENTRIES = 10_000


class Stepwise[S](Protocol):
    """Модель навыка, оценка которой идёт по наблюдению за шаг: `estimate` равна `result` от
    `step` по всем наблюдениям, начиная с `begin`. Сейчас — модуль `app.adapter.irt`."""

    def initial(self, prior: Prior) -> SkillEstimate: ...

    def advance(
        self, prior: Prior, levels: SkillProfileLevels, now: datetime
    ) -> SkillProfileLevels: ...

    def begin(self, prior: Prior) -> S: ...

    def step(self, prior: Prior, state: S, obs: Observation, *, to_mode: bool = False) -> S: ...

    def result(self, state: S) -> SkillEstimate: ...


class PrefixCachedSkillModel[S]:
    """Порт `SkillModel` поверх пошаговой модели с кэшем префиксов не больше `max_entries`
    записей. Один на процесс — его держит точка сборки; потоки HTTP делят записи под замком."""

    def __init__(self, model: Stepwise[S], *, max_entries: int) -> None:
        if max_entries < 1:
            raise ValueError("кэшу нужна хотя бы одна запись")
        self._model = model
        self._max_entries = max_entries
        self._entries: OrderedDict[Hashable, tuple[int, S]] = OrderedDict()
        self._next_id = 0
        self._lock = threading.Lock()

    def __len__(self) -> int:
        return len(self._entries)

    def initial(self, prior: Prior) -> SkillEstimate:
        return self._model.initial(prior)

    def advance(
        self, prior: Prior, levels: SkillProfileLevels, now: datetime
    ) -> SkillProfileLevels:
        return self._model.advance(prior, levels, now)

    def estimate(
        self, prior: Prior, observations: Iterable[Observation], *, to_mode: bool = False
    ) -> SkillEstimate:
        model, observations = self._model, list(observations)
        root: Hashable = (prior, to_mode)
        # Под замком — только поиск и вставка: шаги модели долгие, потоки HTTP их не ждут.
        with self._lock:
            found = self._touch(root)
            done = 0
            if found is not None:
                for obs in observations:
                    child = self._touch((found[0], obs))
                    if child is None:
                        break
                    found, done = child, done + 1
        start = model.begin(prior) if found is None else found[1]
        state, states = start, []
        for obs in observations[done:]:
            state = model.step(prior, state, obs, to_mode=to_mode)
            states.append(state)
        if found is None or states:
            with self._lock:
                # Пока считали, другой поток мог вставить ту же ветку: запись заменится, старые
                # потомки станут недостижимы и уйдут по LRU.
                node = self._add(root, start) if found is None else found[0]
                for obs, step_state in zip(observations[done:], states, strict=True):
                    node = self._add((node, obs), step_state)
        return model.result(state)

    def _touch(self, key: Hashable) -> tuple[int, S] | None:
        found = self._entries.get(key)
        if found is not None:
            self._entries.move_to_end(key)
        return found

    def _add(self, key: Hashable, state: S) -> int:
        self._next_id += 1
        self._entries[key] = (self._next_id, state)
        if len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)
        return self._next_id
