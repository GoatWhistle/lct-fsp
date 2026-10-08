"""Реестр ФСП — реализации порта `FspRegistry`.

`FileFspRegistry` — заглушка реестра: JSON-файл достижений по ФСП ID на синтетических данных,
`{"<ФСП ID>": [{event, date, discipline, place, fsp_result, team_role}]}`. Состав полей — наше
предложение ФСП (docs/glossary.md). Файл читается при каждом запросе: перегенерированный файл
виден без перезапуска. Настоящий реестр — новый адаптер рядом, сценарии не меняются.
"""

import datetime as dt
from pathlib import Path

from pydantic import BaseModel, ConfigDict, RootModel, ValidationError

from app.domain.errors import FspRegistryUnavailable
from app.domain.fsp import FspAchievement, FspResult


class _Achievement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event: str
    date: dt.date
    discipline: str
    place: int | None
    fsp_result: FspResult
    team_role: str | None


_RegistryFile = RootModel[dict[str, list[_Achievement]]]


def _domain(row: _Achievement) -> FspAchievement:
    return FspAchievement(
        event=row.event,
        date=row.date,
        discipline=row.discipline,
        place=row.place,
        result=row.fsp_result,
        team_role=row.team_role,
    )


class FileFspRegistry:
    def __init__(self, path: Path) -> None:
        self._path = path

    def achievements(self, fsp_id: str) -> list[FspAchievement]:
        try:
            data = _RegistryFile.model_validate_json(self._path.read_bytes()).root
        except (OSError, ValidationError) as error:
            # Нет файла или он испорчен — для сценария это недоступный реестр.
            raise FspRegistryUnavailable() from error
        return [_domain(row) for row in data.get(fsp_id, [])]


class MemoryFspRegistry:
    """Реестр в памяти для тестов: достижения кладёт тест, `available = False` — реестр не
    отвечает."""

    def __init__(self) -> None:
        self.records: dict[str, list[FspAchievement]] = {}
        self.available = True

    def achievements(self, fsp_id: str) -> list[FspAchievement]:
        if not self.available:
            raise FspRegistryUnavailable()
        return list(self.records.get(fsp_id, []))
