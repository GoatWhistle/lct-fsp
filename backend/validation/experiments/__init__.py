from collections.abc import Sequence

from settings import Mechanics


def with_overrides(base: Mechanics, pairs: Sequence[str]) -> Mechanics:
    """Механики с правками `имя=значение` — через валидацию, чтобы значение имело тот же тип,
    что в конфиге; неизвестное имя или значение вне допустимого — ошибка."""
    found = dict(pair.split("=", 1) for pair in pairs)
    unknown = sorted(set(found) - set(Mechanics.model_fields))
    if unknown:
        raise SystemExit(f"нет такого параметра механик: {', '.join(unknown)}")
    return Mechanics.model_validate({**base.model_dump(), **found})
