import json
from datetime import date
from functools import cache
from pathlib import Path
from typing import Any

from app.domain.catalog import CatalogRef
from app.domain.locale import Locale

BRAND_DIR = Path(__file__).parent


@cache
def _tree(locale: Locale) -> dict[str, Any]:
    words: dict[str, Any] = json.loads((BRAND_DIR / "words" / f"{locale}.json").read_text("utf-8"))
    words["catalog"] = json.loads((BRAND_DIR / f"catalog.{locale}.json").read_text("utf-8"))
    return words


def _plural(locale: Locale, count: int) -> str:
    if locale != "ru":
        return "one" if count == 1 else "many"
    if count % 10 == 1 and count % 100 != 11:
        return "one"
    if 2 <= count % 10 <= 4 and not 12 <= count % 100 <= 14:
        return "few"
    return "many"


def _number(locale: Locale, value: float) -> str:
    text = f"{value:.1f}"
    return text.replace(".", ",") if locale == "ru" else text


class Words:
    def __init__(self, locale: Locale) -> None:
        self.locale = locale
        self._tree = _tree(locale)

    def __call__(self, key: str, **values: object) -> str:
        node: Any = self._tree
        for part in key.split("."):
            node = node[part]
        return str(node).format(**values)

    def has(self, key: str) -> bool:
        node: Any = self._tree
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                return False
            node = node[part]
        return isinstance(node, str)

    def catalog(self, kind: str, ref: CatalogRef | str) -> str:
        code = ref if isinstance(ref, str) else ref.code
        names = self._tree["catalog"].get(kind, {})
        name = names.get(code) if isinstance(names, dict) else None
        if isinstance(name, str):
            return name
        return ref if isinstance(ref, str) else ref.name

    def date(self, day: date) -> str:
        month = self._tree["months"][day.month - 1]
        return self("date", day=day.day, month=month, year=day.year)

    def years(self, count: int) -> str:
        if count == 0:
            return self("pdf.years.lessThanYear")
        return self(f"pdf.years.{_plural(self.locale, count)}", n=count)

    def half_years(self, years: float) -> str:
        if years < 0.5:
            return self("pdf.years.lessThanHalf")
        if years == 0.5:
            return self("pdf.years.half")
        if years != int(years):
            return self("pdf.years.fraction", n=_number(self.locale, years))
        return self.years(int(years))
