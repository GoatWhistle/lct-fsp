"""HTML, CSS и вёрстка: блочная модель, единицы, специфичность, flex и grid, селекторы.

Эталон считает модель правил CSS ровно для конструкций шаблона — так, как их вычисляет браузер.
"""

import random

from app.domain.bank.family import Instance, rounded

PX_PROMPT = "Ответ — числа в пикселях через пробел, без «px»."


def box_width(rng: random.Random) -> Instance:
    boxes = []
    widths = []
    for name in ("first", "second"):
        width, padding = rng.randrange(100, 400, 10), rng.randint(0, 30)
        border, margin = rng.randint(0, 8), rng.randint(0, 25)
        sizing = rng.choice(["content-box", "border-box"])
        boxes.append(
            f".{name} {{ box-sizing: {sizing}; width: {width}px; padding: 0 {padding}px; "
            f"border: {border}px solid; margin: 0 {margin}px; }}"
        )
        outer = width if sizing == "border-box" else width + 2 * padding + 2 * border
        widths.append(outer + 2 * margin)
    prompt = (
        "Сколько места по горизонтали займёт каждый блок вместе с внешними отступами (margin)? "
        + PX_PROMPT
    )
    return Instance(prompt, " ".join(map(str, widths)), {"boxes": boxes}, code="\n".join(boxes))


def rem_em(rng: random.Random) -> Instance:
    root = rng.choice([10, 12, 14, 16, 18, 20])
    outer = rng.choice([1.25, 1.5, 2, 0.75])
    inner = rng.choice([1.5, 2, 0.5, 0.8])
    rem = rng.choice([0.5, 1.5, 2, 2.5])
    padding = rng.choice([0.5, 1, 2])
    code = (
        f"html {{ font-size: {root}px; }}\n"
        f".card {{ font-size: {outer}em; }}\n"
        f".card .title {{ font-size: {inner}em; padding: {padding}em; }}\n"
        f".card .note {{ font-size: {rem}rem; }}\n"
    )
    card = root * outer
    title = card * inner
    values = [title, title * padding, root * rem]
    prompt = (
        "Блок .card вложен прямо в body, .title и .note — прямо в .card. Каковы font-size у "
        ".title, его padding и font-size у .note? " + PX_PROMPT
    )

    def fmt(x: float) -> str:
        return f"{x:g}"

    params = {"root": root, "outer": outer, "inner": inner, "rem": rem, "padding": padding}
    return Instance(prompt, " ".join(fmt(v) for v in values), params, code=code)


def _selector(rng: random.Random) -> tuple[str, tuple[int, int, int]]:
    ids = classes = tags = 0
    parts = []
    for _ in range(rng.randint(1, 3)):
        piece = ""
        if rng.random() < 0.6:
            piece += rng.choice(["div", "ul", "li", "a", "span", "nav", "p"])
            tags += 1
        if rng.random() < 0.25:
            piece += "#" + rng.choice(["main", "menu", "cart"])
            ids += 1
        for _ in range(rng.choice([0, 0, 1, 2])):
            piece += rng.choice([".item", ".active", "[href]", ":hover", ":first-child"])
            classes += 1
        if not piece:
            piece = rng.choice(["li", "a"])
            tags += 1
        parts.append(piece)
    # Псевдоэлемент — только в конце последней части селектора.
    if rng.random() < 0.2:
        parts[-1] += "::before"
        tags += 1
    return rng.choice([" ", " > "]).join(parts), (ids, classes, tags)


def specificity(rng: random.Random) -> Instance:
    selectors = [_selector(rng) for _ in range(3)]
    lines = [f"{i}. {s}" for i, (s, _) in enumerate(selectors, 1)]
    prompt = (
        "Какова специфичность каждого селектора? Запишите её тремя цифрами подряд: число id, "
        "число классов, атрибутов и псевдоклассов, число тегов и псевдоэлементов — например 012. "
        "Ответ — три таких записи через пробел."
    )
    answer = " ".join("".join(map(str, spec)) for _, spec in selectors)
    return Instance(prompt, answer, {"selectors": [s for s, _ in selectors]}, code="\n".join(lines))


def flex_grow(rng: random.Random) -> Instance:
    items = [(rng.randrange(40, 160, 10), rng.randint(0, 3)) for _ in range(3)]
    gap = rng.choice([0, 10, 20])
    container = sum(b for b, _ in items) + 2 * gap + rng.randrange(40, 600, 10)
    free = container - sum(b for b, _ in items) - gap * 2
    grow = sum(g for _, g in items)
    widths = [b + (free * g / grow if grow else 0) for b, g in items]
    code = f".row {{ display: flex; width: {container}px; gap: {gap}px; }}\n" + "\n".join(
        f".item{i} {{ flex: {g} 0 {b}px; }}" for i, (b, g) in enumerate(items, 1)
    )
    prompt = (
        "В .row три пустых дочерних элемента .item1, .item2, .item3 без рамок и отступов. Какой "
        "ширины они станут? Ответ — числа в пикселях через пробел, при необходимости округлите до "
        "десятых."
    )
    return Instance(
        prompt,
        " ".join(f"{rounded(w, 1)}".rstrip("0").rstrip(".") for w in widths),
        {"container": container, "items": items, "gap": gap},
        code=code,
    )


def nth_child(rng: random.Random) -> Instance:
    count = rng.randint(8, 12)
    a, b = rng.choice(
        [
            (2, 1),
            (2, 0),
            (3, 1),
            (3, 2),
            (4, 1),
            (-1, 4),
            (-1, 5),
            (0, 3),
            (3, 0),
            (2, 3),
            (4, 3),
            (5, 0),
            (-2, 7),
            (3, 4),
            (-1, 3),
            (5, 2),
        ]
    )
    if a == 0:
        formula = str(b)
    elif a == -1:
        formula = f"-n+{b}"
    else:
        formula = f"{a}n+{b}" if b else f"{a}n"
    matched = [
        i
        for i in range(1, count + 1)
        if (a == 0 and i == b) or (a != 0 and (i - b) % a == 0 and (i - b) // a >= 0)
    ]
    last = rng.random() < 0.4
    if last:
        matched = [count + 1 - i for i in reversed(matched)]
    pseudo = "nth-last-child" if last else "nth-child"
    prompt = (
        f"В списке ul {count} элементов li. Какие из них выберет селектор li:{pseudo}({formula})? "
        "Ответ — номера элементов с начала списка, от 1, через пробел по возрастанию."
    )
    params = {"count": count, "a": a, "b": b, "last": last}
    return Instance(prompt, " ".join(map(str, matched)), params)


def margin_collapse(rng: random.Random) -> Instance:
    pairs = []
    gaps = []
    for _ in range(2):
        bottom, top = rng.randint(-20, 60), rng.randint(-20, 60)
        pairs.append((bottom, top))
        positives = [m for m in (bottom, top) if m > 0]
        negatives = [m for m in (bottom, top) if m < 0]
        gaps.append((max(positives) if positives else 0) + (min(negatives) if negatives else 0))
    code = "\n".join(
        f"/* пара {i} */ .a{i} {{ margin-bottom: {b}px; }} .b{i} {{ margin-top: {t}px; }}"
        for i, (b, t) in enumerate(pairs, 1)
    )
    prompt = (
        "Блоки .a1 и .b1, .a2 и .b2 — соседние блочные элементы в обычном потоке, без рамок и "
        "padding. Какое расстояние будет между нижним краем .a и верхним краем .b в каждой паре? "
        "Ответ — два числа в пикселях через пробел."
    )
    return Instance(prompt, " ".join(map(str, gaps)), {"pairs": pairs}, code=code)


def flex_shrink(rng: random.Random) -> Instance:
    container = rng.randrange(300, 600, 20)
    items = [(rng.randrange(150, 350, 10), rng.randint(1, 3)) for _ in range(3)]
    overflow = sum(b for b, _ in items) - container
    if overflow <= 0:
        container = sum(b for b, _ in items) - rng.randrange(60, 200, 10)
        overflow = sum(b for b, _ in items) - container
    weight = sum(b * s for b, s in items)
    widths = [b - overflow * b * s / weight for b, s in items]
    code = f".row {{ display: flex; width: {container}px; }}\n" + "\n".join(
        f".item{i} {{ flex: 0 {s} {b}px; }}" for i, (b, s) in enumerate(items, 1)
    )
    prompt = (
        "В .row три пустых элемента без рамок и отступов. Они не помещаются — какой ширины "
        "станут после сжатия? Ответ — числа в пикселях через пробел, округлите до десятых."
    )
    answer = " ".join(f"{rounded(w, 1)}".rstrip("0").rstrip(".") for w in widths)
    return Instance(prompt, answer, {"container": container, "items": items}, code=code)


def grid_fr(rng: random.Random) -> Instance:
    width = rng.randrange(600, 1400, 20)
    fixed = rng.randrange(80, 240, 20)
    fr = [rng.randint(1, 3), rng.randint(1, 3)]
    gap = rng.choice([0, 8, 16, 24])
    free = width - fixed - 2 * gap
    columns = [fixed] + [free * f / sum(fr) for f in fr]
    code = (
        f".grid {{ display: grid; width: {width}px; gap: {gap}px;\n"
        f"        grid-template-columns: {fixed}px {fr[0]}fr {fr[1]}fr; }}"
    )
    prompt = (
        "Какой ширины будут три колонки сетки, если содержимое колонок узкое? Ответ — числа в "
        "пикселях через пробел, округлите до десятых."
    )
    answer = " ".join(f"{rounded(c, 1)}".rstrip("0").rstrip(".") for c in columns)
    return Instance(
        prompt, answer, {"width": width, "fixed": fixed, "fr": fr, "gap": gap}, code=code
    )


def media_queries(rng: random.Random) -> Instance:
    base = rng.randint(12, 16)
    rules = [("", base)]
    for _ in range(3):
        bound = rng.randrange(400, 1400, 100)
        kind = rng.choice(["min-width", "max-width"])
        rules.append((f"({kind}: {bound}px)", rng.randint(10, 24)))
    viewports = sorted(rng.sample(range(320, 1600, 20), 4))

    def applies(cond: str, width: int) -> bool:
        if not cond:
            return True
        kind, bound = cond.strip("()").split(": ")
        value = int(bound.removesuffix("px"))
        return width >= value if kind == "min-width" else width <= value

    sizes = [[size for cond, size in rules if applies(cond, w)][-1] for w in viewports]
    code = "\n".join(
        f".text {{ font-size: {size}px; }}"
        if not cond
        else f"@media {cond} {{ .text {{ font-size: {size}px; }} }}"
        for cond, size in rules
    )
    prompt = (
        f"Каким будет font-size у .text при ширине окна {', '.join(map(str, viewports))} px? "
        "Правила идут в файле в этом порядке. " + PX_PROMPT
    )
    return Instance(
        prompt, " ".join(map(str, sizes)), {"rules": rules, "viewports": viewports}, code=code
    )


def sibling_selectors(rng: random.Random) -> Instance:
    matched: list[int] = []
    while not matched:
        tags = [rng.choice(["p", "p", "div", "span", "h2"]) for _ in range(11)]
        marked = rng.sample(range(11), rng.randint(2, 3))
        combinator = rng.choice(["+", "~"])
        target = rng.choice(["p", "div", "span"])
        matched = [
            i + 1
            for i, tag in enumerate(tags)
            if tag == target
            and (i - 1 in marked if combinator == "+" else any(m < i for m in marked))
        ]
    html = "\n".join(
        f"<{t}{' class="x"' if i in marked else ''}>{i + 1}</{t}>" for i, t in enumerate(tags)
    )
    prompt = (
        f"Элементы ниже — соседи внутри одного родителя. Какие из них выберет селектор "
        f".x {combinator} {target}? Ответ — числа внутри выбранных элементов через пробел."
    )
    params = {"tags": tags, "marked": marked, "combinator": combinator, "target": target}
    return Instance(prompt, " ".join(map(str, matched)), params, code=html)


def absolute_position(rng: random.Random) -> Instance:
    outer = (rng.randrange(0, 200, 10), rng.randrange(0, 200, 10))
    middle = (rng.randrange(10, 100, 10), rng.randrange(10, 100, 10))
    positioned = rng.choice(["relative", "static"])
    inner = (rng.randrange(5, 60, 5), rng.randrange(5, 60, 5))
    code = (
        f'<div class="outer" style="position: relative; top: {outer[0]}px; left: {outer[1]}px">\n'
        f'  <div class="middle" style="position: {positioned}; '
        f'top: {middle[0]}px; left: {middle[1]}px">\n'
        f'    <div class="inner" style="position: absolute; '
        f'top: {inner[0]}px; left: {inner[1]}px"></div>\n'
        "  </div>\n"
        "</div>"
    )
    # У static top и left не действуют, и такой блок не служит опорным для absolute.
    shift = middle if positioned == "relative" else (0, 0)
    top, left = (o + s + i for o, s, i in zip(outer, shift, inner, strict=True))
    prompt = (
        ".outer — первый элемент body, у html и body нет отступов, ни у одного блока нет "
        "margin, padding и рамок. На каком расстоянии от верхнего и левого края страницы "
        "окажется .inner? Ответ — два числа в пикселях через пробел: сверху и слева."
    )
    params = {"outer": outer, "middle": middle, "positioned": positioned, "inner": inner}
    return Instance(prompt, f"{top} {left}", params, code=code)


def percent_padding(rng: random.Random) -> Instance:
    width = rng.randrange(300, 1200, 20)
    height = rng.randrange(100, 600, 20)
    ratio = rng.choice([25, 50, 56.25, 75, 100])
    inner = rng.choice([10, 20, 30])
    code = (
        f".box {{ width: {width}px; height: {height}px; }}\n"
        f".box .ratio {{ height: 0; padding-top: {ratio}%; }}\n"
        f".box .pad {{ padding: {inner}% 0; }}\n"
    )
    values = [width * ratio / 100, 2 * width * inner / 100]
    prompt = (
        ".ratio и .pad — блочные дети .box без содержимого. Какова полная высота .ratio и "
        "суммарный вертикальный padding у .pad? Ответ — два числа в пикселях через пробел, "
        "округлите до десятых."
    )
    answer = " ".join(f"{rounded(v, 1)}".rstrip("0").rstrip(".") for v in values)
    return Instance(
        prompt,
        answer,
        {"width": width, "height": height, "ratio": ratio, "inner": inner},
        code=code,
    )
