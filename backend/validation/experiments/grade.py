"""Эксперимент этапа 3: определение грейда честных кандидатов при изменённой механике.

Меряет на настроечном наборе (сид D3) долю занижения, завышения, точного совпадения, длину
теста и стабильность повтора. Меняется один параметр механики за прогон: `--set имя=значение`.
"""

import argparse
import statistics
from collections.abc import Sequence
from dataclasses import dataclass

from app.adapter.catalog_file import load_catalog
from settings import CATALOG_FILE, MECHANICS_FILE, Mechanics
from validation.commands import _pool, honesty, stability
from validation.market import TUNING_SEED, market, warm


@dataclass(frozen=True)
class Row:
    code: str
    over: float
    exact: float
    agreement: float
    kappa: float
    median_items: float
    at_limit: float
    sd_z: float


def _run(job: tuple[str, int, Mechanics, int, int]) -> Row:
    code, seed, mechanics, candidates, pairs = job
    m = warm(market(code, mechanics, seed))
    h = honesty(m, candidates)
    st = stability(m, pairs)
    return Row(
        code,
        st.overestimate,
        st.exact,
        st.agreement,
        st.kappa,
        statistics.median(h.lengths),
        sum(n >= mechanics.test_max_items for n in h.lengths) / len(h.lengths),
        statistics.pstdev(h.z),
    )


def measure(mechanics: Mechanics, seed: int, candidates: int, pairs: int) -> list[Row]:
    codes = [s.code for s in load_catalog(CATALOG_FILE).specializations]
    with _pool() as pool:
        return list(pool.map(_run, [(c, seed, mechanics, candidates, pairs) for c in codes]))


def main(argv: Sequence[str] | None = None) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=TUNING_SEED)
    p.add_argument("--candidates", type=int, default=300)
    p.add_argument("--pairs", type=int, default=300)
    p.add_argument("--set", action="append", default=[], metavar="имя=значение")
    args = p.parse_args(argv)
    base = Mechanics.from_yaml(MECHANICS_FILE)
    update = {k: type(getattr(base, k))(v) for k, v in (s.split("=") for s in args.set)}
    rows = measure(base.model_copy(update=update), args.seed, args.candidates, args.pairs)
    n = len(rows)

    def f(attr: str) -> float:
        return float(sum(getattr(r, attr) for r in rows) / n)

    print(
        f"seed={args.seed} {update or 'config'} | over={f('over'):.3f} "
        f"under={1 - f('over') - f('exact'):.3f} exact={f('exact'):.3f} "
        f"agree={f('agreement'):.3f} kappa={f('kappa'):.3f} items={f('median_items'):.1f} "
        f"limit={f('at_limit'):.2f} sd_z={f('sd_z'):.3f}"
    )


if __name__ == "__main__":
    main()
