"""Двойники кандидатов набора для M3 и M5 (docs/validation-plan.md): тот же кандидат с той же
истиной и теми же ответами, другое только в резюме.

- M3 — двойник честного кандидата под потребность: дописал в самоописание и стек весь стек и
  название потребности. Пары — `M3_PER_NEED` честных кандидатов на потребность.
- M5 — двойник с другим полом (по имени), другой группой возраста и вуза
  (`population.opposite`). Кандидатов — `M5_CANDIDATES` на набор, поровну по специализациям.

Выборка — из потоков `random.Random` с сидом набора и ключом: тот же набор — те же двойники.
Кого брать в M3, решает экспериментатор по персонажу из истины; платформа и базовые линии видят
только наблюдаемое двойника.
"""

import enum
import random
import uuid
from dataclasses import dataclass, replace

from app.domain.need import NeedForm
from validation.main import Catalog
from validation.population import Dataset, ObservedCandidate, opposite
from validation.truth import Persona

M3_PER_NEED = 30
M5_CANDIDATES = 500
NAMESPACE = uuid.UUID("6f1d3c52-8c1e-4d0a-9a51-7d0b6d1f0b7e")


class TwinKind(enum.StrEnum):
    inflated = "m3"
    protected = "m5"


@dataclass(frozen=True)
class Twin:
    id: uuid.UUID
    source: uuid.UUID
    kind: TwinKind
    # M3 — потребность, под которую дописано резюме; M5 — None.
    need: uuid.UUID | None
    observed: ObservedCandidate


def inflate(o: ObservedCandidate, form: NeedForm, catalog: Catalog) -> ObservedCandidate:
    """Резюме, дописанное под потребность: весь её стек и её название."""
    stack = (*o.stack, *(t for t in form.stack if t not in o.stack))
    names = ", ".join(catalog.technologies[t].name for t in form.stack)
    return replace(o, stack=stack, about=f"{o.about} {form.title}. Стек: {names}.")


def twins(
    dataset: Dataset,
    catalog: Catalog,
    *,
    per_need: int = M3_PER_NEED,
    protected: int = M5_CANDIDATES,
) -> tuple[Twin, ...]:
    seed = dataset.params.seed
    truth = {t.id: t for t in dataset.truths}
    by_spec: dict[str, list[ObservedCandidate]] = {}
    for o in dataset.observed:
        by_spec.setdefault(o.specialization, []).append(o)
    found: list[Twin] = []
    for need in dataset.needs:
        honest = [
            o
            for o in by_spec.get(need.form.specialization, [])
            if truth[o.id].persona == Persona.honest
        ]
        rng = random.Random(f"{seed}:m3:{need.id}")
        for o in sorted(rng.sample(honest, min(per_need, len(honest))), key=lambda o: o.id):
            twin_id = uuid.uuid5(NAMESPACE, f"m3:{need.id}:{o.id}")
            seen = replace(inflate(o, need.form, catalog), id=twin_id)
            found.append(Twin(twin_id, o.id, TwinKind.inflated, need.id, seen))
    share = protected // max(1, len(by_spec))
    for code in sorted(by_spec):
        rng = random.Random(f"{seed}:m5:{code}")
        own = by_spec[code]
        for o in sorted(rng.sample(own, min(share, len(own))), key=lambda o: o.id):
            twin_id = uuid.uuid5(NAMESPACE, f"m5:{o.id}")
            person = opposite(o.person, o.experience_years, random.Random(f"{seed}:{twin_id}"))
            found.append(
                Twin(twin_id, o.id, TwinKind.protected, None, replace(o, id=twin_id, person=person))
            )
    return tuple(found)
