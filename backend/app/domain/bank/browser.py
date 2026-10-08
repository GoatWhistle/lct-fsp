"""Браузер, сеть и производительность: загрузка ресурсов, порядок скриптов, всплытие событий,
debounce и throttle, same-origin, кэш, кадры и длинные задачи."""

import math
import random
from urllib.parse import urljoin, urlsplit

from app.domain.bank.family import Instance, rounded
from app.domain.bank.runner import CodeRunner


def parallel_downloads(rng: random.Random, runner: CodeRunner) -> Instance:
    files = rng.randint(6, 30)
    per_host = rng.choice([2, 4, 6])
    duration = rng.randrange(40, 200, 10)
    hosts = rng.randint(1, 2)
    per = math.ceil(files / hosts)
    total = math.ceil(per / per_host) * duration
    prompt = (
        f"Страница грузит {files} картинок по HTTP/1.1, они поровну разложены по доменам "
        f"(доменов: {hosts}). Браузер держит не больше {per_host} соединений на домен, каждая "
        f"картинка грузится {duration} мс, запросы стартуют сразу, как освободится соединение. "
        "Через сколько миллисекунд загрузится последняя картинка? Ответ — число."
    )
    params = {"files": files, "per_host": per_host, "duration": duration, "hosts": hosts}
    return Instance(prompt, str(total), params)


def url_resolution(rng: random.Random, runner: CodeRunner) -> Instance:
    base = rng.choice(
        [
            "https://shop.example/catalog/phones/index.html",
            "https://shop.example/catalog/phones/",
            "https://shop.example/blog/2026/post",
        ]
    )
    refs = rng.sample(
        [
            "img/a.png",
            "./b.css",
            "../c.js",
            "/d.json",
            "../../e.html",
            "?page=2",
            "#top",
            "f/../g.txt",
        ],
        3,
    )
    resolved = [urlsplit(urljoin(base, ref)) for ref in refs]
    answers = [
        r.path + (f"?{r.query}" if r.query else "") + (f"#{r.fragment}" if r.fragment else "")
        for r in resolved
    ]
    prompt = (
        f"Документ загружен с адреса {base}. В какие пути превратятся относительные ссылки "
        f"{', '.join(refs)}? Ответ — пути с ведущим слешем (с ?запросом и #якорем, если они есть) "
        "через пробел по порядку."
    )
    return Instance(prompt, " ".join(answers), {"base": base, "refs": refs})


def script_order(rng: random.Random, runner: CodeRunner) -> Instance:
    """Модель: все загрузки стартуют в 0 (сканер предзагрузки), скрипт i загружен к моменту
    load_i. Разбор HTML мгновенный, синхронный скрипт останавливает его до своей загрузки.
    inline и синхронный выполняются, когда до них дошёл разбор; async — по загрузке, но не раньше,
    чем разбор дошёл до тега; defer и module — после разбора, по порядку документа.

    Экземпляры с одновременной готовностью двух скриптов и с async, загруженным раньше, чем
    разбор дошёл до тега, отбрасываются: там порядок зависит от браузера.
    """
    while True:
        kinds = [
            rng.choice(["sync", "defer", "async", "inline", "module"])
            for _ in range(rng.randint(4, 5))
        ]
        loads = [10 * x for x in rng.sample(range(1, 20), len(kinds))]
        parser = 0
        moments: list[int] = []
        ambiguous = False
        for kind, load in zip(kinds, loads, strict=True):
            if kind == "sync":
                parser = max(parser, load)
            if kind in ("inline", "sync"):
                moments.append(parser)
            elif kind == "async":
                ambiguous = ambiguous or load <= parser
                moments.append(load)
            else:
                moments.append(-1)
        ready = parser
        for i, kind in enumerate(kinds):
            if kind in ("defer", "module"):
                ready = max(ready, loads[i])
                # Отложенные идут после разбора и друг за другом: ничья с ними — не ничья.
                moments[i] = ready
        deferred = [i for i, kind in enumerate(kinds) if kind in ("defer", "module")]
        timed = [m for i, m in enumerate(moments) if i not in deferred]
        if not ambiguous and len(set(timed)) == len(timed):
            break
    names = "ABCDE"[: len(kinds)]
    # Отложенные выполняются после всех, кто готов к концу разбора, в порядке документа.
    order = sorted(
        range(len(kinds)),
        key=lambda i: (moments[i], i in deferred, i),
    )
    lines = []
    for name, kind, load in zip(names, kinds, loads, strict=True):
        if kind == "inline":
            lines.append(f"<script>log('{name}')</script>")
        else:
            attr = {"sync": "", "defer": " defer", "async": " async", "module": ' type="module"'}
            lines.append(
                f'<script{attr[kind]} src="{name.lower()}.js"></script>'
                f"  <!-- загрузится к {load} мс, печатает {name} -->"
            )
    prompt = (
        "Скрипты стоят в HTML в этом порядке. Загрузки всех файлов начинаются в момент 0 "
        "параллельно, разбор HTML и выполнение мгновенны. В каком порядке они напечатают буквы? "
        "Ответ — буквы подряд."
    )
    return Instance(
        prompt,
        "".join(names[i] for i in order),
        {"kinds": kinds, "loads": loads},
        code="\n".join(lines),
    )


def event_propagation(rng: random.Random, runner: CodeRunner) -> Instance:
    levels = ["outer", "middle", "inner"]
    listeners = []
    for el in levels:
        for phase in ("capture", "bubble"):
            if rng.random() < 0.65:
                stop = rng.random() < 0.15
                listeners.append((el, phase, stop))
    if not listeners:
        listeners.append(("inner", "bubble", False))
    log: list[str] = []
    stopped = False
    for el in levels:  # погружение: сверху вниз
        if stopped:
            break
        for name, phase, stop in listeners:
            if name == el and phase == "capture":
                log.append(f"{el[0].upper()}c")
                stopped = stopped or stop
    if not stopped:
        for el in reversed(levels):  # всплытие: снизу вверх
            if stopped:
                break
            for name, phase, stop in listeners:
                if name == el and phase == "bubble":
                    log.append(f"{el[0].upper()}b")
                    stopped = stopped or stop
    code = "\n".join(
        f"{el}.addEventListener('click', e => {{ log('{el[0].upper()}{phase[0]}');"
        + (" e.stopPropagation();" if stop else "")
        + f" }}{', true' if phase == 'capture' else ''});"
        for el, phase, stop in listeners
    )
    prompt = (
        "inner лежит в middle, middle — в outer. Пользователь кликнул по inner. Что окажется в "
        "логе? Ответ — записи через пробел по порядку."
    )
    return Instance(prompt, " ".join(log), {"listeners": listeners}, code=code)


def debounce_calls(rng: random.Random, runner: CodeRunner) -> Instance:
    wait = rng.choice([100, 200, 300])
    # Шаг 70 мс: паузы не совпадают с задержкой ровно — без ничьих таймера и нажатия.
    moments = sorted(rng.sample(range(0, 1500, 70), rng.randint(6, 9)))
    calls = []
    for i, t in enumerate(moments):
        nxt = moments[i + 1] if i + 1 < len(moments) else None
        if nxt is None or nxt - t >= wait:
            calls.append(t + wait)
    prompt = (
        f"Обработчик ввода обёрнут в debounce с задержкой {wait} мс (вызов по завершении паузы). "
        f"Пользователь нажимал клавиши в моменты {', '.join(map(str, moments))} мс. В какие "
        "моменты вызовется обработчик? Ответ — числа через пробел."
    )
    return Instance(prompt, " ".join(map(str, calls)), {"wait": wait, "moments": moments})


def throttle_calls(rng: random.Random, runner: CodeRunner) -> Instance:
    wait = rng.choice([100, 200, 300])
    moments = sorted(rng.sample(range(0, 1200, 25), rng.randint(7, 10)))
    calls, last = [], None
    for t in moments:
        if last is None or t - last >= wait:
            calls.append(t)
            last = t
    prompt = (
        f"Обработчик прокрутки обёрнут в throttle на {wait} мс: событие вызывает обработчик, "
        f"только если с прошлого вызова прошло не меньше {wait} мс, иначе отбрасывается. События "
        f"пришли в моменты {', '.join(map(str, moments))} мс. В какие моменты вызовется "
        "обработчик? Ответ — числа через пробел."
    )
    return Instance(prompt, " ".join(map(str, calls)), {"wait": wait, "moments": moments})


def same_origin(rng: random.Random, runner: CodeRunner) -> Instance:
    base = "https://app.example.ru"
    candidates = [
        "https://app.example.ru/profile",
        "https://app.example.ru:443/api",
        "http://app.example.ru/api",
        "https://api.example.ru/v1",
        "https://app.example.ru:8443/",
        "https://example.ru/",
        "https://app.example.ru/../admin",
        "https://APP.example.ru/docs",
    ]
    picked = rng.sample(candidates, 6)

    def origin(url: str) -> tuple[str, str, int]:
        parts = urlsplit(url)
        port = parts.port or (443 if parts.scheme == "https" else 80)
        return parts.scheme, (parts.hostname or "").lower(), port

    answers = ["да" if origin(u) == origin(base) else "нет" for u in picked]
    prompt = (
        f"Страница открыта с {base}/. Для каждого адреса ниже: тот же ли это origin? Ответ — "
        "«да» или «нет» через пробел по порядку."
    )
    return Instance(prompt, " ".join(answers), {"urls": picked}, code="\n".join(picked))


def critical_path(rng: random.Random, runner: CodeRunner) -> Instance:
    html = rng.randint(50, 300)
    css = rng.randint(50, 300)
    font = rng.randint(50, 300)
    script = rng.randint(50, 300)
    blocking = rng.choice(["sync", "defer"])
    # Первая отрисовка ждёт HTML, CSS и, если скрипт синхронный в head, — скрипт.
    first_paint = html + max(css, script if blocking == "sync" else 0)
    text_paint = max(first_paint, html + css + font)
    code = (
        "<head>\n"
        f'  <link rel="stylesheet" href="app.css">   <!-- {css} мс -->\n'
        f'  <script {"defer " if blocking == "defer" else ""}src="app.js"></script>'
        f"   <!-- {script} мс -->\n"
        "</head>\n"
        "<!-- шрифт подключён в app.css через @font-face, font-display: block, грузится "
        f"{font} мс после того, как получен CSS -->"
    )
    prompt = (
        f"HTML грузится {html} мс, затем ресурсы из head начинают грузиться параллельно; "
        "выполнение и разбор мгновенны. Через сколько миллисекунд от начала будет первая "
        "отрисовка страницы и когда станет виден текст со шрифтом? Ответ — два числа через пробел."
    )
    params = {"html": html, "css": css, "font": font, "script": script, "blocking": blocking}
    return Instance(prompt, f"{first_paint} {text_paint}", params, code=code)


def layout_shift(rng: random.Random, runner: CodeRunner) -> Instance:
    viewport = rng.choice([(800, 600), (1000, 800), (400, 800)])
    shifts = []
    total = 0.0
    for _ in range(rng.randint(2, 3)):
        width_share = rng.choice([0.25, 0.5, 0.75, 1.0])
        height = rng.randrange(50, viewport[1] // 2, 10)
        distance = rng.randrange(10, 200, 10)
        # Объединение старого и нового положения: при сдвиге больше высоты — два прямоугольника.
        impact = width_share * (height + min(distance, height)) / viewport[1]
        distance_fraction = distance / max(viewport)
        score = impact * distance_fraction
        total += score
        shifts.append((width_share, height, distance))
    lines = [
        f"{i}. блок шириной {int(w * 100)} % окна, высотой {h} px сдвинулся вниз на {d} px"
        for i, (w, h, d) in enumerate(shifts, 1)
    ]
    prompt = (
        f"Окно {viewport[0]}×{viewport[1]} px, все сдвиги — в одном окне сессии, блоки "
        "целиком в окне и до, и после сдвига. Сдвиг даёт доля воздействия (площадь объединения "
        "старого и нового положения / площадь окна) × доля расстояния (сдвиг / большая сторона "
        "окна). Каков CLS? Ответ — число, округлите до тысячных."
    )
    params = {"viewport": viewport, "shifts": shifts}
    return Instance(prompt, f"{rounded(total, 3)}", params, code="\n".join(lines))


def cache_directives(rng: random.Random, runner: CodeRunner) -> Instance:
    max_age = rng.choice([30, 60, 90])
    swr = rng.choice([0, 0, 60, 120])
    directive = f"max-age={max_age}" + (f", stale-while-revalidate={swr}" if swr else "")
    moments = sorted(rng.sample(range(10, 400, 10), rng.randint(6, 7)))
    stored = 0
    letters = []
    for t in moments:
        age = t - stored
        if age < max_age:
            letters.append("К")
        elif age < max_age + swr:
            letters.append("Ф")
            stored = t
        else:
            # Устаревший ответ с ETag проверяется условным запросом, 304 освежает его.
            letters.append("П")
            stored = t
    prompt = (
        f"Ответ сервера пришёл в момент 0 с Cache-Control: {directive} и ETag; сервер отвечает "
        "мгновенно, ресурс не меняется. Браузер запрашивает его снова в моменты "
        f"{', '.join(map(str, moments))} с. Что происходит при каждом запросе? Ответ — по букве "
        "подряд: К — из кэша без сети, П — условный запрос на сервер перед использованием, Ф — "
        "из кэша, а проверка в фоне."
    )
    return Instance(prompt, "".join(letters), {"directive": directive, "moments": moments})


def long_tasks(rng: random.Random, runner: CodeRunner) -> Instance:
    tasks = [rng.choice([5, 10, 20, 30, 45, 60, 80, 120, 200]) for _ in range(rng.randint(5, 8))]
    blocking = sum(max(0, t - 50) for t in tasks)
    long_count = sum(1 for t in tasks if t > 50)
    prompt = (
        f"После первой отрисовки в главном потоке выполнились задачи длительностью "
        f"{', '.join(map(str, tasks))} мс. Сколько среди них длинных задач и каков Total Blocking "
        "Time (сумма превышений над 50 мс)? Ответ — два числа через пробел."
    )
    return Instance(prompt, f"{long_count} {blocking}", {"tasks": tasks})


def service_worker(rng: random.Random, runner: CodeRunner) -> Instance:
    strategy = rng.choice(["cache-first", "network-first", "stale-while-revalidate"])
    start = rng.randint(1, 9)
    cached = network = start
    served = []
    lines = []
    for i in range(1, 7):
        if rng.random() < 0.4:
            network += 1
            lines.append(f"на сервере выложили v{network}")
        online = rng.random() < 0.7
        lines.append(f"запрос {i}, сеть {'есть' if online else 'нет'}")
        if strategy == "network-first" and online:
            cached = network
        served.append(cached)
        if strategy == "stale-while-revalidate" and online:
            cached = network
    prompt = (
        f"Service worker отдаёт app.js по стратегии {strategy}; сначала в кэше v{start}. Сеть, "
        "когда она есть, отвечает мгновенно, полученный из сети ответ кладётся в кэш. Какие "
        "версии получит страница? Ответ — номера версий без v через пробел по порядку запросов."
    )
    params = {"strategy": strategy, "start": start, "events": lines}
    return Instance(prompt, " ".join(map(str, served)), params, code="\n".join(lines))
