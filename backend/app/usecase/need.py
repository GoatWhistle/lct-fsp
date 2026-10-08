"""Сценарии потребностей работодателя: список, заведение, правка, удаление и важность тем по
стеку до сохранения (mechanics.md, §12).

Работодатель видит и меняет только свои потребности: чужая для него не существует — 404, а не
403, чтобы не раскрывать, что такая есть (`NeedNotFound` из хранилища). Правила формы — в
`app.domain.need`.
"""

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.domain.catalog import Specialization, Technology
from app.domain.importance import TopicImportance
from app.domain.need import (
    NeedForm,
    NeedRecord,
    NeedTerms,
    TopicView,
    check_edited_topics,
    known_specialization,
    known_stack,
    need_terms,
    topic_views,
)
from app.usecase.interface import CatalogRepository, Clock, NeedRepository, UnitOfWork


@dataclass(frozen=True)
class NeedView:
    record: NeedRecord
    # Все темы специализации по порядку.
    topics: list[TopicView]


class Needs:
    def __init__(
        self,
        uow: UnitOfWork,
        needs: NeedRepository,
        catalog: CatalogRepository,
        clock: Clock,
        *,
        key_min_technologies: int,
    ) -> None:
        self._uow = uow
        self._needs = needs
        self._catalog = catalog
        self._clock = clock
        self._key_min = key_min_technologies

    def all(self, user_id: uuid.UUID) -> list[NeedView]:
        """Потребности работодателя, новые сверху."""
        with self._uow:
            return [self._view(record) for record in self._needs.records(user_id)]

    def get(self, user_id: uuid.UUID, need_id: uuid.UUID) -> NeedView:
        with self._uow:
            return self._view(self._needs.record(user_id, need_id))

    def create(self, user_id: uuid.UUID, form: NeedForm) -> NeedView:
        with self._uow:
            need_id = self._needs.add(user_id, self._terms(form), self._clock.now())
            return self._view(self._needs.record(user_id, need_id))

    def update(self, user_id: uuid.UUID, need_id: uuid.UUID, form: NeedForm) -> NeedView:
        """Заменяет потребность целиком; чужая проверяется раньше формы."""
        with self._uow:
            self._needs.ensure(user_id, need_id)
            self._needs.replace(user_id, need_id, self._terms(form), self._clock.now())
            return self._view(self._needs.record(user_id, need_id))

    def delete(self, user_id: uuid.UUID, need_id: uuid.UUID) -> None:
        with self._uow:
            self._needs.delete(user_id, need_id)

    def preview_topics(
        self,
        specialization: str,
        stack: Sequence[str],
        edited: Mapping[str, TopicImportance],
    ) -> list[TopicView]:
        """Важность тем по стеку до сохранения — форма показывает её, пока работодатель
        выбирает."""
        with self._uow:
            known = known_specialization(self._catalog.specialization(specialization))
            technologies = known_stack(stack, self._catalog.technologies(stack))
        check_edited_topics(known, edited)
        return self._topics(known, technologies, edited)

    def _terms(self, form: NeedForm) -> NeedTerms:
        return need_terms(
            form,
            self._catalog.specialization(form.specialization),
            self._catalog.grade(form.grade),
            self._catalog.technologies(form.stack),
        )

    def _view(self, record: NeedRecord) -> NeedView:
        need = record.need
        return NeedView(
            record, self._topics(need.specialization, need.stack, need.edited_importance)
        )

    def _topics(
        self,
        specialization: Specialization,
        stack: Sequence[Technology],
        edited: Mapping[str, TopicImportance],
    ) -> list[TopicView]:
        return topic_views(specialization, stack, edited, key_min_technologies=self._key_min)
