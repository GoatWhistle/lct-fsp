"""Картинки отчёта стенда — SVG текстом, без библиотек графиков: тот же вход — тот же файл байт в
байт."""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from validation.metrics import Bin

# Цвета серий по порядку: до поправки, после.
COLORS = ("#b45309", "#1d4ed8", "#047857")
# Цвета серий распределений: наша выдача, B1, B2, B3.
SERIES_COLORS = ("#111827", "#b45309", "#1d4ed8", "#047857")
SIZE = 220
PAD = 34


@dataclass(frozen=True)
class Series:
    label: str
    bins: Sequence[Bin]


@dataclass(frozen=True)
class Panel:
    title: str
    # Подписи осей: предсказано и наблюдаемо.
    x: str
    y: str
    series: Sequence[Series]


def _n(x: float) -> str:
    return f"{x:.1f}"


def reliability_svg(title: str, panels: Sequence[Panel]) -> str:
    """Надёжностная диаграмма: по панели на часть метрики, по ломаной на серию — средняя
    наблюдаемая доля против средней предсказанной вероятности в непустых корзинах, размер точки —
    по доле наблюдений корзины. Диагональ — идеальная калибровка."""
    width = PAD + len(panels) * (SIZE + PAD * 2)
    legend_y = SIZE + PAD * 3 + 6
    height = legend_y + 12 * len(panels[0].series) + 8
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="sans-serif" font-size="11">',
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        f'<text x="{PAD}" y="18" font-size="13" font-weight="bold">{title}</text>',
    ]
    for i, panel in enumerate(panels):
        left = PAD + i * (SIZE + PAD * 2) + PAD
        top = PAD + 10

        def at(px: float, py: float, left: float = left, top: float = top) -> tuple[str, str]:
            return _n(left + px * SIZE), _n(top + (1 - py) * SIZE)

        out.append(f'<text x="{left}" y="{top - 6}" font-weight="bold">{panel.title}</text>')
        out.append(
            f'<rect x="{left}" y="{top}" width="{SIZE}" height="{SIZE}" fill="none" '
            'stroke="#9ca3af"/>'
        )
        for tick in (0.0, 0.5, 1.0):
            x, _ = at(tick, 0)
            _, y = at(0, tick)
            out.append(
                f'<text x="{x}" y="{_n(top + SIZE + 13)}" text-anchor="middle">{tick}</text>'
            )
            out.append(f'<text x="{_n(left - 4)}" y="{y}" text-anchor="end">{tick}</text>')
        (x1, y1), (x2, y2) = at(0, 0), at(1, 1)
        out.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#9ca3af" '
            'stroke-dasharray="4 3"/>'
        )
        out.append(
            f'<text x="{_n(left + SIZE / 2)}" y="{_n(top + SIZE + 27)}" '
            f'text-anchor="middle">{panel.x}</text>'
        )
        out.append(
            f'<text x="{_n(left - 26)}" y="{_n(top + SIZE / 2)}" text-anchor="middle" '
            f'transform="rotate(-90 {_n(left - 26)} {_n(top + SIZE / 2)})">{panel.y}</text>'
        )
        for series, color in zip(panel.series, COLORS, strict=False):
            filled = [b for b in series.bins if b.count]
            total = sum(b.count for b in filled)
            points = [at(b.confidence, b.accuracy) for b in filled]
            out.append(
                f'<polyline fill="none" stroke="{color}" stroke-width="1.5" points="'
                + " ".join(f"{x},{y}" for x, y in points)
                + '"/>'
            )
            for b, (x, y) in zip(filled, points, strict=True):
                radius = 1.5 + 4 * math.sqrt(b.count / total)
                out.append(f'<circle cx="{x}" cy="{y}" r="{_n(radius)}" fill="{color}"/>')
    for j, series in enumerate(panels[0].series):
        row = legend_y + 12 * j
        out.append(
            f'<rect x="{PAD}" y="{row - 8}" width="10" height="10" fill="{COLORS[j]}"/>'
            f'<text x="{PAD + 16}" y="{row}">{series.label}</text>'
        )
    out.append("</svg>")
    return "\n".join(out) + "\n"


def ecdf_svg(
    title: str, panels: Sequence[tuple[str, Sequence[tuple[str, Sequence[float]]]]], x: str
) -> str:
    """Эмпирические функции распределения: по панели на набор, по ступенчатой линии на серию.
    Ось X — от −100 до 100, ось Y — доля значений не больше x. Серия без значений не рисуется,
    но остаётся в легенде с пометкой «нет данных»."""
    width = PAD + len(panels) * (SIZE + PAD * 2)
    names = [label for label, _ in panels[0][1]]
    legend_y = SIZE + PAD * 3 + 6
    height = legend_y + 12 * len(names) + 8
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="sans-serif" font-size="11">',
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        f'<text x="{PAD}" y="18" font-size="13" font-weight="bold">{title}</text>',
    ]
    for i, (panel_title, series) in enumerate(panels):
        left = PAD + i * (SIZE + PAD * 2) + PAD
        top = PAD + 10

        def at(px: float, py: float, left: float = left, top: float = top) -> tuple[str, str]:
            return _n(left + (px + 100) / 200 * SIZE), _n(top + (1 - py) * SIZE)

        out.append(f'<text x="{left}" y="{top - 6}" font-weight="bold">{panel_title}</text>')
        out.append(
            f'<rect x="{left}" y="{top}" width="{SIZE}" height="{SIZE}" fill="none" '
            'stroke="#9ca3af"/>'
        )
        for xtick in (-100, 0, 100):
            tx, _ = at(xtick, 0)
            out.append(
                f'<text x="{tx}" y="{_n(top + SIZE + 13)}" text-anchor="middle">{xtick}</text>'
            )
        for tick in (0.0, 0.5, 1.0):
            _, ty = at(-100, tick)
            out.append(f'<text x="{_n(left - 4)}" y="{ty}" text-anchor="end">{tick}</text>')
        (x1, y1), (x2, y2) = at(0, 0), at(0, 1)
        out.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#9ca3af" '
            'stroke-dasharray="4 3"/>'
        )
        out.append(
            f'<text x="{_n(left + SIZE / 2)}" y="{_n(top + SIZE + 27)}" '
            f'text-anchor="middle">{x}</text>'
        )
        for (_, values), color in zip(series, SERIES_COLORS, strict=False):
            if not values:
                continue
            ordered = sorted(values)
            n = len(ordered)
            points = [at(-100, 0)]
            for k, v in enumerate(ordered):
                points += [at(v, k / n), at(v, (k + 1) / n)]
            points.append(at(100, 1))
            out.append(
                f'<polyline fill="none" stroke="{color}" stroke-width="1.5" points="'
                + " ".join(f"{px},{py}" for px, py in points)
                + '"/>'
            )
    for j, name in enumerate(names):
        row = legend_y + 12 * j
        empty = all(not dict(series)[name] for _, series in panels)
        out.append(
            f'<rect x="{PAD}" y="{row - 8}" width="10" height="10" fill="{SERIES_COLORS[j]}"/>'
            f'<text x="{PAD + 16}" y="{row}">{name}{" — нет данных" if empty else ""}</text>'
        )
    out.append("</svg>")
    return "\n".join(out) + "\n"
