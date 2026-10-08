"""Видимый текст резюме из PDF на `pypdf` — реализация порта `ResumeText` (mechanics.md, §16).

Скрытый текст вырезается до извлечения: обход потока содержимого страницы повторяет состояние
графики — матрицы, цвет и его пространство, прозрачность, режим отрисовки, кегль, интервалы и
подъём — и выбрасывает показ текста, который человек на странице не увидит. Затем `pypdf`
извлекает текст из того, что осталось, — так разбор видит то, что видит человек.

Скрытым считается текст: светлее `max_lightness` на белом с учётом прозрачности, в невидимом
режиме отрисовки, с кеглем на странице меньше `min_font_pt` — с учётом матриц и горизонтального
сжатия, — с началом за пределами видимой области страницы, в том числе после сдвига кернингом
`TJ` или подъёмом `Ts`, и с межбуквенным или межсловным интервалом больше `MAX_SPACING_EM` кегля:
такими интервалами буквы разносят за край. Ширина глифов не считается: строка, которая начинается
на странице и сама уходит за край, остаётся. Текст под картинкой, за обрезкой или мягкой маской
не ловится: такой приём виден в редакторе, а вклад самоописания ограничен сверху всё равно
(`self_reported_stack_cap`).

Распакованное содержимое всех страниц и форм — не больше `max_content_bytes`: иначе маленький
сжатый файл раздувается в сотни мегабайт операторов.
"""

import io
import logging
import math
from dataclasses import dataclass, field, replace
from typing import Any

from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    ContentStream,
    DecodedStreamObject,
    DictionaryObject,
    EncodedStreamObject,
    NameObject,
    StreamObject,
)

from app.domain.errors import ResumeTooLarge, ResumeUnreadable, ResumeWithoutText

type Matrix = tuple[float, float, float, float, float, float]

IDENTITY: Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
# Операторы показа текста.
SHOW = {b"Tj", b"TJ", b"'", b'"'}
# Режимы отрисовки текста: 3 — невидимый, 7 — только обрезка.
INVISIBLE_MODES = {3, 7}
FILL_MODES = {0, 2, 4, 6}
STROKE_MODES = {1, 2, 5, 6}
# Вложенность форм XObject глубже — не обходится: так не зациклить форму, ссылающуюся на себя.
MAX_FORM_DEPTH = 8
# Интервал между буквами или словами больше стольких кеглей не встречается в обычном наборе.
MAX_SPACING_EM = 2.0


class _Space:
    """Как читать компоненты цвета: по числу компонент (серый, RGB, CMYK), как оттенок краски
    (Separation, DeviceN: 0 — краски нет, белое) или никак — тогда цвет считается видимым."""

    device = "device"
    tint = "tint"
    unknown = "unknown"


DEVICE_SPACES = {"/DeviceGray", "/DeviceRGB", "/DeviceCMYK", "/CalGray", "/CalRGB", "/ICCBased"}

# pypdf шумит предупреждениями о мелких нарушениях формата — для резюме это не ошибка.
logging.getLogger("pypdf").setLevel(logging.ERROR)


def _times(m: Matrix, n: Matrix) -> Matrix:
    """m × n в соглашении PDF: точка сначала преобразуется m, затем n."""
    a, b, c, d, e, f = m
    a2, b2, c2, d2, e2, f2 = n
    return (
        a * a2 + b * c2,
        a * b2 + b * d2,
        c * a2 + d * c2,
        c * b2 + d * d2,
        e * a2 + f * c2 + e2,
        e * b2 + f * d2 + f2,
    )


def _numbers(operands: list[Any]) -> list[float]:
    return [float(x) for x in operands if isinstance(x, int | float)]


def _number(operands: list[Any]) -> float | None:
    numbers = _numbers(operands)
    return numbers[0] if len(numbers) == 1 else None


def _matrix(operands: list[Any]) -> Matrix | None:
    match _numbers(operands):
        case [a, b, c, d, e, f]:
            return (a, b, c, d, e, f)
        case _:
            return None


def _resource(resources: Any, kind: str, name: Any) -> Any:
    """Объект ресурса страницы или формы по имени; нет такого — `None`, а не ошибка."""
    try:
        return resources[kind][name].get_object()
    except (KeyError, TypeError, AttributeError):
        return None


def _space(resources: Any, operands: list[Any]) -> str:
    """Вид цветового пространства из `cs`/`CS`: имя устройства или ресурс `/ColorSpace`."""
    name = operands[0] if operands else None
    family = name
    if str(name) not in DEVICE_SPACES:
        found = _resource(resources, "/ColorSpace", name)
        family = found[0] if isinstance(found, ArrayObject) and found else found
    if str(family) in DEVICE_SPACES:
        return _Space.device
    if str(family) in {"/Separation", "/DeviceN"}:
        return _Space.tint
    return _Space.unknown


def _rewrite(stream: StreamObject, data: bytes) -> None:
    """Новые данные потока. pypdf сжимает заново только FlateDecode — поток с другим фильтром
    переводится на него."""
    if isinstance(stream, EncodedStreamObject):
        stream[NameObject("/Filter")] = NameObject("/FlateDecode")
        stream.pop("/DecodeParms", None)
        stream.decoded_self = DecodedStreamObject()
    stream.set_data(data)


def _lightness(components: list[float], space: str = _Space.device) -> float:
    """Светлота цвета 0…1. Узор и неизвестное пространство считаются тёмными: видимыми."""
    if space == _Space.tint:
        return 1 - sum(components) / len(components) if components else 0.0
    if space == _Space.unknown:
        return 0.0
    match components:
        case [gray]:
            return gray
        case [r, g, b]:
            return 0.299 * r + 0.587 * g + 0.114 * b
        case [c, m, y, k]:
            return 0.299 * (1 - c) * (1 - k) + 0.587 * (1 - m) * (1 - k) + 0.114 * (1 - y) * (1 - k)
        case _:
            return 0.0


@dataclass(frozen=True)
class _State:
    """Состояние графики, которое решает, виден ли текст. Текстовые параметры — тоже часть
    состояния графики: `q`/`Q` их сохраняют и восстанавливают."""

    ctm: Matrix = IDENTITY
    fill: float = 0.0
    stroke: float = 0.0
    fill_space: str = _Space.device
    stroke_space: str = _Space.device
    fill_alpha: float = 1.0
    stroke_alpha: float = 1.0
    font_size: float = 0.0
    scale: float = 100.0
    leading: float = 0.0
    char_spacing: float = 0.0
    word_spacing: float = 0.0
    rise: float = 0.0
    mode: int = 0


@dataclass(frozen=True)
class _Box:
    left: float
    bottom: float
    right: float
    top: float


@dataclass
class _Budget:
    """Счётчики на весь документ: показы текста, распакованные байты и обойдённые формы."""

    max_content_bytes: int
    shown: int = 0
    content_bytes: int = 0
    seen_forms: set[int] = field(default_factory=set)

    def spend(self, data: bytes) -> None:
        self.content_bytes += len(data)
        if self.content_bytes > self.max_content_bytes:
            raise ResumeTooLarge()


class _Filter:
    """Обход потока содержимого с вырезанием скрытого текста."""

    def __init__(
        self, pdf: PdfWriter, box: _Box, min_font_pt: float, max_lightness: float, budget: _Budget
    ) -> None:
        self._pdf = pdf
        self._box = box
        self._min_font = min_font_pt
        self._max_lightness = max_lightness
        self._budget = budget

    def run(self, content: ContentStream, resources: Any, state: _State, depth: int = 0) -> None:
        stack: list[_State] = []
        tm = tlm = IDENTITY
        kept: list[tuple[list[Any], bytes]] = []
        for operands, operator in content.operations:
            match operator:
                case b"q":
                    stack.append(state)
                case b"Q":
                    state = stack.pop() if stack else state
                case b"cm":
                    if m := _matrix(operands):
                        state = replace(state, ctm=_times(m, state.ctm))
                case b"g" | b"rg" | b"k":
                    state = replace(
                        state, fill=_lightness(_numbers(operands)), fill_space=_Space.device
                    )
                case b"G" | b"RG" | b"K":
                    state = replace(
                        state, stroke=_lightness(_numbers(operands)), stroke_space=_Space.device
                    )
                case b"sc" | b"scn":
                    state = replace(state, fill=_lightness(_numbers(operands), state.fill_space))
                case b"SC" | b"SCN":
                    state = replace(
                        state, stroke=_lightness(_numbers(operands), state.stroke_space)
                    )
                # Начальный цвет пространства — чёрный, у оттенка краски — полный тон.
                case b"cs":
                    state = replace(state, fill=0.0, fill_space=_space(resources, operands))
                case b"CS":
                    state = replace(state, stroke=0.0, stroke_space=_space(resources, operands))
                case b"gs":
                    state = self._ext_state(state, resources, operands)
                case b"BT":
                    tm = tlm = IDENTITY
                case b"Tf":
                    if (n := _number(operands)) is not None:
                        state = replace(state, font_size=n)
                case b"Tz":
                    if (n := _number(operands)) is not None:
                        state = replace(state, scale=n)
                case b"TL":
                    if (n := _number(operands)) is not None:
                        state = replace(state, leading=n)
                case b"Tc":
                    if (n := _number(operands)) is not None:
                        state = replace(state, char_spacing=n)
                case b"Tw":
                    if (n := _number(operands)) is not None:
                        state = replace(state, word_spacing=n)
                case b"Ts":
                    if (n := _number(operands)) is not None:
                        state = replace(state, rise=n)
                case b"Tr":
                    if (n := _number(operands)) is not None:
                        state = replace(state, mode=int(n))
                case b"Tm":
                    if m := _matrix(operands):
                        tm = tlm = m
                case b"Td" | b"TD":
                    if len(n2 := _numbers(operands)) == 2:
                        if operator == b"TD":
                            state = replace(state, leading=-n2[1])
                        tm = tlm = _times((1, 0, 0, 1, n2[0], n2[1]), tlm)
                case b"T*":
                    tm = tlm = _times((1, 0, 0, 1, 0, -state.leading), tlm)
                case b'"':
                    if len(n2 := _numbers(operands[:2])) == 2:
                        state = replace(state, word_spacing=n2[0], char_spacing=n2[1])
                case b"Do":
                    self._form(resources, operands, state, depth)
            if operator in {b"'", b'"'}:
                tm = tlm = _times((1, 0, 0, 1, 0, -state.leading), tlm)
            if operator in SHOW:
                shown = self._shown(operator, operands, state, tm)
                if shown is None:
                    # Переход на новую строку у «'» и «"» остаётся, сам текст — нет.
                    if operator in {b"'", b'"'}:
                        kept.append(([], b"T*"))
                    continue
                self._budget.shown += 1
                operands = shown
            kept.append((operands, operator))
        content.operations = kept

    def _shown(
        self, operator: bytes, operands: list[Any], state: _State, tm: Matrix
    ) -> list[Any] | None:
        """Что из показа текста видно: операнды как есть, у `TJ` — без строк, которые кернинг
        увёл за край, или `None` — не видно ничего."""
        if not self._styled_visible(state, tm):
            return None
        if operator != b"TJ":
            return operands if self._at(state, tm, 0.0) else None
        parts = operands[0] if operands and isinstance(operands[0], list) else []
        shift = 0.0
        visible: list[Any] = []
        for part in parts:
            if isinstance(part, int | float):
                # Смещение в тысячных долях кегля, со знаком «минус» — вправо.
                shift -= float(part) / 1000 * state.font_size * state.scale / 100
                visible.append(part)
            elif self._at(state, tm, shift):
                visible.append(part)
        if not any(not isinstance(p, int | float) for p in visible):
            return None
        return [ArrayObject(visible), *operands[1:]]

    def _styled_visible(self, state: _State, tm: Matrix) -> bool:
        """Виден ли текст при этом цвете, прозрачности, режиме, кегле и интервалах."""
        if state.mode in INVISIBLE_MODES:
            return False
        colors = []
        if state.mode in FILL_MODES:
            colors.append((state.fill, state.fill_alpha))
        if state.mode in STROKE_MODES:
            colors.append((state.stroke, state.stroke_alpha))
        # На белом листе полупрозрачный цвет светлеет: почти прозрачный чёрный — почти белый.
        if not any(1 - alpha * (1 - light) <= self._max_lightness for light, alpha in colors):
            return False
        size = abs(state.font_size)
        limit = MAX_SPACING_EM * size
        if abs(state.char_spacing) > limit or abs(state.word_spacing) > limit:
            return False
        a, b, c, d, _, _ = _times(tm, state.ctm)
        height = size * math.hypot(c, d)
        width = size * state.scale / 100 * math.hypot(a, b)
        return min(height, width) >= self._min_font

    def _at(self, state: _State, tm: Matrix, shift: float) -> bool:
        """Попадает ли на страницу точка начала текста, сдвинутая на `shift` вдоль строки и на
        подъём `Ts` поперёк."""
        a, b, c, d, x, y = _times(tm, state.ctm)
        x += shift * a + state.rise * c
        y += shift * b + state.rise * d
        height = abs(state.font_size) * math.hypot(c, d)
        box = self._box
        return box.left <= x < box.right and box.bottom - height < y < box.top

    @staticmethod
    def _ext_state(state: _State, resources: Any, operands: list[Any]) -> _State:
        """Прозрачность заливки и обводки и шрифт с кеглем из словаря `/ExtGState`."""
        ext = _resource(resources, "/ExtGState", operands[0] if operands else None)
        if not isinstance(ext, DictionaryObject):
            return state
        fill = ext.get("/ca", state.fill_alpha)
        stroke = ext.get("/CA", state.stroke_alpha)
        font = ext.get("/Font")
        size = font[1] if isinstance(font, ArrayObject) and len(font) == 2 else None
        return replace(
            state,
            fill_alpha=float(fill) if isinstance(fill, int | float) else state.fill_alpha,
            stroke_alpha=float(stroke) if isinstance(stroke, int | float) else state.stroke_alpha,
            font_size=float(size) if isinstance(size, int | float) else state.font_size,
        )

    def _form(self, resources: Any, operands: list[Any], state: _State, depth: int) -> None:
        """Форма XObject — свой поток содержимого со своими ресурсами: её текст фильтруется с
        состоянием на момент первого `Do` в документе и переписывается на месте. Повторный
        `Do` той же формы видит уже отфильтрованное: видимое второе вхождение скрытой первой
        формы теряется, но скрытое в разбор не попадает."""
        if depth >= MAX_FORM_DEPTH:
            return
        form = _resource(resources, "/XObject", operands[0] if operands else None)
        if not isinstance(form, StreamObject) or form.get("/Subtype") != "/Form":
            return
        if id(form) in self._budget.seen_forms:
            return
        self._budget.seen_forms.add(id(form))
        self._budget.spend(form.get_data())
        if matrix := _matrix(list(form.get("/Matrix", []))):
            state = replace(state, ctm=_times(matrix, state.ctm))
        inner = form.get("/Resources")
        inner = inner.get_object() if inner is not None else resources
        content = ContentStream(form, self._pdf)
        self.run(content, inner, state, depth + 1)
        _rewrite(form, content.get_data())


class PypdfResumeText:
    """Реализация порта `ResumeText` на `pypdf`; сети не касается."""

    def __init__(
        self,
        *,
        max_pages: int,
        max_content_bytes: int,
        min_font_pt: float,
        max_lightness: float,
    ) -> None:
        self._max_pages = max_pages
        self._max_content_bytes = max_content_bytes
        self._min_font = min_font_pt
        self._max_lightness = max_lightness

    def visible_text(self, pdf: bytes) -> str:
        if b"%PDF-" not in pdf[:1024]:
            raise ResumeUnreadable()
        try:
            return self._text(pdf)
        except (ResumeTooLarge, ResumeWithoutText):
            raise
        # Битый PDF роняет pypdf чем угодно — от PdfReadError до KeyError в словаре страницы.
        except Exception as error:
            raise ResumeUnreadable() from error

    def _text(self, pdf: bytes) -> str:
        reader = PdfReader(io.BytesIO(pdf))
        if reader.is_encrypted and not reader.decrypt(""):
            raise ResumeUnreadable()
        if len(reader.pages) > self._max_pages:
            raise ResumeTooLarge()
        # Поток содержимого меняется в копии: у страницы читателя pypdf его не подменяет.
        writer = PdfWriter(clone_from=reader)
        budget = _Budget(self._max_content_bytes)
        texts = []
        for page in writer.pages:
            box = page.cropbox
            visible = _Box(float(box.left), float(box.bottom), float(box.right), float(box.top))
            resources = page.get("/Resources")
            resources = resources.get_object() if resources is not None else DictionaryObject()
            contents = page.get_contents()
            if contents is None:
                continue
            budget.spend(contents.get_data())
            content = ContentStream(contents, writer)
            _Filter(writer, visible, self._min_font, self._max_lightness, budget).run(
                content, resources, _State()
            )
            # Байтами, а не разобранным потоком: из разобранного pypdf извлекает текст без
            # кодировки шрифта.
            filtered = DecodedStreamObject()
            filtered.set_data(content.get_data())
            page.replace_contents(filtered.flate_encode())
            texts.append(page.extract_text())
        text = "\n".join(texts)
        if budget.shown == 0 or not any(ch.isalnum() for ch in text):
            raise ResumeWithoutText()
        return text
