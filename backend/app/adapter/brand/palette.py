import json
from functools import cache
from pathlib import Path

Color = tuple[int, int, int]

TOKENS = Path(__file__).with_name("tokens.json")
WHITE: Color = (255, 255, 255)


@cache
def _colors() -> dict[str, str]:
    colors: dict[str, str] = json.loads(TOKENS.read_text("utf-8"))["colors"]
    return colors


def _over(front: Color, alpha: float, back: Color) -> Color:
    r, g, b = (round(f * alpha + k * (1 - alpha)) for f, k in zip(front, back, strict=True))
    return (r, g, b)


def color(name: str, back: Color = WHITE) -> Color:
    value = _colors()[name].lstrip("#")
    rgb = (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))
    if len(value) == 8:
        return _over(rgb, int(value[6:8], 16) / 255, back)
    return rgb


def hex_color(name: str, back: Color = WHITE) -> str:
    r, g, b = color(name, back)
    return f"#{r:02x}{g:02x}{b:02x}"
