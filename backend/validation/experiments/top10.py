"""Диагностика этапа 3: из кого состоит топ-10 нашей выдачи и B0 и почему часть нерелевантна.

Нерелевантный в топ-10 относится к первой подходящей причине: персонаж-атакующий; блок не
точный; честный с присвоенным грейдом выше истинного; честный на нужном грейде, но с темами
ниже требований (грейд общий, эталон — по темам потребности); прочее.
"""

import argparse
import uuid
from collections import Counter

from settings import MECHANICS_FILE, Mechanics
from validation.report import NAIVE, OURS, DatasetRuns, collect, ranked_lists
from validation.simulate import Scale
from validation.truth import Persona

TOP = 10


def classify(
    data: DatasetRuns,
    need_grade: str,
    need: uuid.UUID,
    c: uuid.UUID,
    placed_block: str,
    pair_grade: int,
    method: str,
) -> str:
    truth = data.truth()[c]
    if pair_grade >= 2:
        return "relevant"
    if truth.persona is not Persona.honest:
        return f"persona:{truth.persona.value}"
    if method == OURS and placed_block != "exact":
        return f"block:{placed_block}"
    order = [None, "intern", "junior", "middle", "senior"]
    if truth.grade is not None and order.index(truth.grade) < order.index(need_grade):
        return "honest:true-grade-below-need"
    return "honest:topics-below-requirements"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--set", default="d1")
    p.add_argument("--candidates", type=int, default=200)
    p.add_argument("--set-opt", action="append", default=[], metavar="имя=значение")
    args = p.parse_args()
    base = Mechanics.from_yaml(MECHANICS_FILE)
    update = {k: type(getattr(base, k))(v) for k, v in (s.split("=") for s in args.set_opt)}
    mechanics = base.model_copy(update=update)
    runs = collect(
        mechanics,
        Scale(candidates=args.candidates, pairs=10, warm=500, compare=10, fit=10),
        sets=(args.set,),
        protection=None,
    )
    data = runs.sets[args.set]
    grades = {n.id: n.form.grade for n in data.dataset.needs}
    for method in (OURS, NAIVE):
        counts: Counter[str] = Counter()
        blocks: Counter[str] = Counter()
        for _, need, ranked, _ in ranked_lists(data, method):
            rows = (x for run in data.runs.values() for x in run.placed.get(need, ()))
            placed = {x.candidate: x.block for x in rows}
            for c in ranked[:TOP]:
                block = placed.get(c, "outside")
                blocks[block] += 1
                grade = data.pairs[need, c].grade
                counts[classify(data, grades[need], need, c, block, grade, method)] += 1
        total = sum(counts.values())
        print(f"{method} {update or 'config'} set={args.set} top{TOP} slots={total}")
        for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
            print(f"  {k}: {v / total:.3f}")
        print("  blocks:", {k: round(v / total, 3) for k, v in blocks.items()})


if __name__ == "__main__":
    main()
