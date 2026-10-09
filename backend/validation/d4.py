"""D4 — ручная разметка (docs/validation-plan.md, «Данные» и M20): 80 пар «потребность —
кандидат» из D1, стратифицированных по специализациям и квинтилям нашего скора, форма разметки и
файлы оценок двух размечающих.

Файлы — в `validation/data/d4/`:

- `sample.jsonl` — пары выборки: номер в форме, потребность, кандидат, специализация, квинтиль;
- `form.md` — рубрика 0–3 и пары: потребность и обезличенная карточка кандидата так, как её
  видит работодатель, — категория, профиль навыков, ФСП, стек; без нашего скора и без ФИО,
  возраста, вуза и контактов;
- `labels-a.csv`, `labels-b.csv` — оценки размечающих: `item,rel`, rel — 0–3. Каждый размечает
  свой файл, не видя чужого.

Выборку пишет команда `report` один раз, если её нет: перезаписывать её после начала разметки
нельзя. M20 считается, когда оба файла оценок заполнены целиком.
"""

import csv
import json
import random
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

D4_DIR = Path(__file__).resolve().parent / "data" / "d4"
SIZE = 80
QUINTILES = 5
SAMPLE = "sample.jsonl"
FORM = "form.md"
RATERS = ("a", "b")
SCALE = 4

RUBRIC = """\
Оцените, насколько кандидат подходит под потребность, по шкале 0–3. Смотрите на требования \
потребности — направление, грейд и стек — и на то, что о кандидате известно: категорию, уровень \
по темам, достижения ФСП и стек.

- **3 — подходит полностью.** Уровень по всем темам, важным для потребности, не ниже требуемого \
грейда; слабых мест, которые помешают работе, не видно.
- **2 — подходит.** Важные темы закрыты; одна-две второстепенные темы ниже требуемого грейда.
- **1 — подходит частично.** Часть важных тем ниже требуемого грейда, но близко к нему; кандидата \
можно рассматривать с оговорками или на грейд ниже.
- **0 — не подходит.** Важные темы заметно ниже требуемого грейда.

Уровень темы — число на общей шкале с погрешностью; пороги грейдов на этой шкале — в шапке \
формы. Чем меньше погрешность, тем увереннее оценка уровня. Оценивайте каждую пару отдельно, не \
сравнивая с соседними. Оценку пишите в свой файл `labels-<буква>.csv`, в столбец `rel` строки с \
номером пары."""


@dataclass(frozen=True)
class Item:
    number: int
    need: uuid.UUID
    candidate: uuid.UUID
    specialization: str
    quintile: int


def _shares(total: int, parts: int) -> list[int]:
    """`total` на `parts` частей поровну, остаток — первым частям."""
    return [total // parts + (i < total % parts) for i in range(parts)]


def draw(
    scored: Mapping[str, Sequence[tuple[uuid.UUID, uuid.UUID, float]]], seed: int, size: int = SIZE
) -> list[Item]:
    """Выборка по специализациям поровну, внутри — по квинтилям скора поровну, старшие квинтили —
    первыми на остаток. `scored` — по специализации пары со скором: (потребность, кандидат, S).
    Порядок в форме перемешан: размечающий не видит страт."""
    codes = sorted(scored)
    drawn: list[tuple[uuid.UUID, uuid.UUID, str, int]] = []
    for code, count in zip(codes, _shares(size, len(codes)), strict=True):
        ordered = sorted(scored[code], key=lambda x: (x[2], x[0], x[1]))
        bins: list[list[tuple[uuid.UUID, uuid.UUID, float]]] = [[] for _ in range(QUINTILES)]
        for i, pair in enumerate(ordered):
            bins[i * QUINTILES // len(ordered)].append(pair)
        # Квинтилю не хватило пар — недобор переходит в следующий.
        short = 0
        for q, take in zip(range(QUINTILES - 1, -1, -1), _shares(count, QUINTILES), strict=True):
            rng = random.Random(f"{seed}:d4:{code}:{q}")
            want = take + short
            got = rng.sample(bins[q], min(want, len(bins[q])))
            short = want - len(got)
            drawn += [(need, candidate, code, q + 1) for need, candidate, _ in got]
    if len(drawn) < size:
        raise ValueError(f"пар со скором на выборку D4 не хватает: {len(drawn)} из {size}")
    random.Random(f"{seed}:d4").shuffle(drawn)
    return [Item(i + 1, *row) for i, row in enumerate(drawn)]


def write_sample(items: Sequence[Item], directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    rows = (
        {
            "item": it.number,
            "need": str(it.need),
            "candidate": str(it.candidate),
            "specialization": it.specialization,
            "quintile": it.quintile,
        }
        for it in items
    )
    (directory / SAMPLE).write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )
    for rater in RATERS:
        lines = ["item,rel"] + [f"{it.number}," for it in items]
        (directory / f"labels-{rater}.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_sample(directory: Path) -> list[Item] | None:
    path = directory / SAMPLE
    if not path.exists():
        return None
    found = []
    for line in path.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        found.append(
            Item(
                r["item"],
                uuid.UUID(r["need"]),
                uuid.UUID(r["candidate"]),
                r["specialization"],
                r["quintile"],
            )
        )
    return found


def load_labels(directory: Path, rater: str) -> dict[int, int]:
    """Заполненные оценки размечающего: номер пары → 0–3. Нет файла — пусто."""
    path = directory / f"labels-{rater}.csv"
    if not path.exists():
        return {}
    found = {}
    with path.open(encoding="utf-8") as file:
        for row in csv.DictReader(file):
            value = (row.get("rel") or "").strip()
            if not value:
                continue
            rel = int(value)
            if not 0 <= rel < SCALE:
                raise ValueError(f"{path.name}, пара {row['item']}: оценка {rel} вне 0–3")
            found[int(row["item"])] = rel
    return found


@dataclass(frozen=True)
class Card:
    """Что размечающий видит о паре: потребность и обезличенная карточка кандидата строками."""

    need: str
    category: str
    # (тема, уровень, погрешность).
    profile: Sequence[tuple[str, float, float]]
    fsp: Sequence[str]
    stack: str


def form(items: Sequence[Item], cards: Mapping[int, Card], scale: str) -> str:
    def n(x: float) -> str:
        return f"{x:.2f}".replace(".", ",").replace("-", "−")

    parts = [
        "# D4 — форма разметки",
        "",
        RUBRIC,
        "",
        f"**Шкала уровня.** {scale}",
    ]
    for it in items:
        card = cards[it.number]
        rows = "\n".join(
            f"| {topic} | {n(level)} | ± {n(sd)} |" for topic, level, sd in card.profile
        )
        fsp = "\n".join(f"- {line}" for line in card.fsp) if card.fsp else "Истории ФСП нет."
        parts += [
            "",
            f"## Пара {it.number}",
            "",
            f"**Потребность.** {card.need}",
            "",
            f"**Кандидат.** Категория: {card.category}. Стек: {card.stack}.",
            "",
            "| Тема | Уровень | Погрешность |",
            "|---|---|---|",
            rows,
            "",
            f"**ФСП.**\n\n{fsp}",
        ]
    return "\n".join(parts) + "\n"
