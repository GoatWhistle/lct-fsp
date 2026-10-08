"""Компонентные фреймворки и состояние: React 18 — обновления состояния, эффекты, мемоизация,
ключи списков, редьюсеры.

Эталон считает модель поведения React ровно для конструкций шаблона: батчинг обновлений,
функциональные обновления, сравнение зависимостей по Object.is, ключи при сверке списков.
"""

import random
from typing import Any

from app.domain.bank.family import Instance, Kind, kind
from app.domain.bank.runner import CodeRunner

PROMPT = "Ответ — значения через пробел по порядку."


@kind(Kind.TRACE)
def state_batching(rng: random.Random, runner: CodeRunner) -> Instance:
    plain, functional = rng.randint(1, 3), rng.randint(0, 3)
    step = rng.randint(1, 5)
    clicks = rng.randint(1, 4)
    start = rng.randint(0, 20)
    calls = [f"setCount(count + {step});"] * plain + [f"setCount(c => c + {step});"] * functional
    rng.shuffle(calls)
    count = start
    for _ in range(clicks):
        # Очередь обновлений одного клика: обычное берёт count этой отрисовки, функциональное —
        # результат предыдущего обновления в очереди.
        value = count
        for call in calls:
            value = (value if "c =>" in call else count) + step
        count = value
    code = (
        "function Counter() {\n"
        f"  const [count, setCount] = useState({start});\n"
        "  function handleClick() {\n" + "".join(f"    {c}\n" for c in calls) + "  }\n"
        "  return <button onClick={handleClick}>{count}</button>;\n"
        "}\n"
    )
    prompt = f"Пользователь нажал кнопку {clicks} раз. Какое число покажет кнопка? Ответ — число."
    return Instance(
        prompt, str(count), {"calls": calls, "clicks": clicks, "start": start}, code=code
    )


@kind(Kind.TRACE)
def list_render(rng: random.Random, runner: CodeRunner) -> Instance:
    items: list[dict[str, Any]] = [
        {
            "id": i,
            "title": rng.choice(["чай", "сыр", "хлеб", "мёд", "рис", "суп"]),
            "price": rng.randint(50, 500),
        }
        for i in rng.sample(range(1, 50), 6)
    ]
    limit = rng.randint(150, 400)
    sort_desc = rng.random() < 0.5
    shown = sorted(
        (it for it in items if it["price"] <= limit),
        key=lambda it: it["price"],
        reverse=sort_desc,
    )
    rendered = ", ".join(
        f"{{ id: {it['id']}, title: '{it['title']}', price: {it['price']} }}" for it in items
    )
    order = "b.price - a.price" if sort_desc else "a.price - b.price"
    code = (
        f"const items = [{rendered}];\n\n"
        "function List() {\n"
        "  return (\n"
        "    <ul>\n"
        f"      {{items.filter(it => it.price <= {limit})\n"
        f"        .sort((a, b) => {order})\n"
        "        .map(it => <li key={it.id}>{it.id}</li>)}\n"
        "    </ul>\n"
        "  );\n"
        "}\n"
    )
    prompt = (
        "Какие числа окажутся в элементах li, сверху вниз? Ответ — числа через пробел; если "
        "список пуст — 0."
    )
    answer = " ".join(str(it["id"]) for it in shown) or "0"
    return Instance(prompt, answer, {"items": items, "limit": limit, "desc": sort_desc}, code=code)


@kind(Kind.TRACE)
def reducer_actions(rng: random.Random, runner: CodeRunner) -> Instance:
    state = {"count": rng.randint(0, 30), "step": rng.randint(1, 4)}
    initial = (
        "const [state, dispatch] = useReducer(reducer, "
        f"{{ count: {state['count']}, step: {state['step']} }});"
    )
    actions = []
    for _ in range(rng.randint(6, 8)):
        kind = rng.choice(["increment", "increment", "decrement", "setStep", "reset", "unknown"])
        if kind == "setStep":
            value = rng.randint(1, 9)
            actions.append(f"{{ type: 'setStep', step: {value} }}")
            state["step"] = value
        else:
            actions.append(f"{{ type: '{kind}' }}")
            if kind == "increment":
                state["count"] += state["step"]
            elif kind == "decrement":
                state["count"] -= state["step"]
            elif kind == "reset":
                state["count"] = 0
    code = (
        "function reducer(state, action) {\n"
        "  switch (action.type) {\n"
        "    case 'increment': return { ...state, count: state.count + state.step };\n"
        "    case 'decrement': return { ...state, count: state.count - state.step };\n"
        "    case 'setStep': return { ...state, step: action.step };\n"
        "    case 'reset': return { ...state, count: 0 };\n"
        "    default: return state;\n"
        "  }\n"
        "}\n\n" + initial + "\n\n// dispatch по порядку:\n" + "\n".join(actions)
    )
    prompt = (
        "Каким станет состояние после всех действий? Ответ — два числа через пробел: count и step."
    )
    return Instance(prompt, f"{state['count']} {state['step']}", {"actions": actions}, code=code)


@kind(Kind.TRACE)
def memo_rerenders(rng: random.Random, runner: CodeRunner) -> Instance:
    # Родитель App с состоянием; дети — memo или нет, получают проп-примитив, объект или колбэк.
    children = []
    for name in rng.sample(["Header", "Sidebar", "List", "Footer", "Badge", "Chart"], 4):
        memo = rng.random() < 0.6
        prop = rng.choice(
            [
                'title="Shop"',
                "user={user}",
                "onClick={handleClick}",
                "count={count}",
                "style={{ color: 'red' }}",
                "onSave={save}",
            ]
        )
        children.append((name, memo, prop))
    lines = [
        "function App() {",
        "  const [count, setCount] = useState(0);",
        "  const user = useMemo(() => ({ name: 'Ann' }), []);",
        "  const save = useCallback(() => {}, []);",
        "  const handleClick = () => setCount(count + 1);",
        "  return (",
        "    <>",
        *[f"      <{name} {prop} />" for name, _, prop in children],
        "    </>",
        "  );",
        "}",
        "",
        *[
            f"const {name} = {'memo(' if memo else ''}function {name}(props) "
            f"{{ /* … */ }}{')' if memo else ''};"
            for name, memo, _ in children
        ],
    ]
    rerender = []
    for name, memo, prop in children:
        stable = prop.startswith(("title=", "user=", "onSave="))
        if not memo or not stable:
            rerender.append(name)
    prompt = (
        "count в App поменялся. Какие из дочерних компонентов отрисуются заново? Ответ — имена "
        "через пробел в порядке разметки; если ни один — 0."
    )
    params = {"children": [[n, m, p] for n, m, p in children]}
    return Instance(prompt, " ".join(rerender) or "0", params, code="\n".join(lines))


@kind(Kind.TRACE)
def effect_runs(rng: random.Random, runner: CodeRunner) -> Instance:
    renders = []
    a = b = 0
    for _ in range(rng.randint(5, 8)):
        if rng.random() < 0.5:
            a += rng.choice([0, 1])
        if rng.random() < 0.5:
            b += rng.choice([0, 1])
        renders.append((a, b))
    deps = {"E1": "[]", "E2": "[a]", "E3": "[a, b]", "E4": "без массива"}
    runs = {name: 0 for name in deps}
    previous: tuple[int, int] | None = None
    for current in renders:
        runs["E4"] += 1
        if previous is None:
            runs["E1"] += 1
            runs["E2"] += 1
            runs["E3"] += 1
        else:
            runs["E2"] += current[0] != previous[0]
            runs["E3"] += current != previous
        previous = current
    code = (
        "function Widget({ a, b }) {\n"
        "  useEffect(() => log('E1'), []);\n"
        "  useEffect(() => log('E2'), [a]);\n"
        "  useEffect(() => log('E3'), [a, b]);\n"
        "  useEffect(() => log('E4'));\n"
        "  return null;\n"
        "}\n\n"
        "// пропсы при последовательных отрисовках (первая — монтирование):\n"
        + "\n".join(f"a = {x}, b = {y}" for x, y in renders)
    )
    prompt = (
        "Strict Mode выключен. Сколько раз выполнится каждый эффект? Ответ — четыре числа через "
        "пробел: E1, E2, E3, E4."
    )
    answer = " ".join(str(runs[n]) for n in deps)
    return Instance(prompt, answer, {"renders": renders}, code=code)


@kind(Kind.TRACE)
def immutable_update(rng: random.Random, runner: CodeRunner) -> Instance:
    qty, price, city = (
        rng.randint(1, 60),
        rng.randint(10, 99),
        rng.choice(["Москва", "Казань", "Пермь"]),
    )
    new_qty = qty + rng.randint(1, 30)
    mutate = rng.random() < 0.5
    if mutate:
        update = f"  next.cart.qty = {new_qty};"
        decl = "  const next = { ...state };"
    else:
        update = f"  next.cart = {{ ...state.cart, qty: {new_qty} }};"
        decl = "  const next = { ...state };"
    code = (
        f"const state = {{ cart: {{ qty: {qty}, price: {price} }}, "
        f"address: {{ city: '{city}' }} }};\n"
        "function update(state) {\n" + decl + "\n" + update + "\n"
        "  return next;\n"
        "}\n"
        "const next = update(state);\n"
        "console.log(state.cart.qty, next === state, next.cart === state.cart, "
        "next.address === state.address);\n"
    )
    old_qty = new_qty if mutate else qty
    answer = f"{old_qty} false {'true' if mutate else 'false'} true"
    prompt = "Что выведет console.log? Ответ — четыре значения через пробел."
    return Instance(prompt, answer, {"qty": qty, "new_qty": new_qty, "mutate": mutate}, code=code)


@kind(Kind.TRACE)
def use_memo_recompute(rng: random.Random, runner: CodeRunner) -> Instance:
    renders = []
    items, sort, query = 0, "asc", "a"
    for _ in range(rng.randint(6, 10)):
        change = rng.choice(["items", "sort", "query", "nothing", "nothing"])
        if change == "items":
            items += 1
        elif change == "sort":
            sort = "desc" if sort == "asc" else "asc"
        elif change == "query":
            query = rng.choice(["a", "b", "c"])
        renders.append((items, sort, query))
    # sorted — новый массив, только когда пересчитан; visible пересчитывается при новом sorted
    # или новом query — то есть при любом изменении трёх пропсов.
    filtered_at = [n for n, current in enumerate(renders, 1) if n == 1 or current != renders[n - 2]]
    code = (
        "function Table({ items, sort, query }) {\n"
        "  const sorted = useMemo(() => sortRows(items, sort), [items, sort]);\n"
        "  const visible = useMemo(() => filterRows(sorted, query), [sorted, query]);\n"
        "  return <Rows rows={visible} />;\n"
        "}\n\n"
        "// отрисовки: версия массива items (новый массив — новая версия), sort, query\n"
        + "\n".join(f"items v{i}, sort = '{s}', query = '{q}'" for i, s, q in renders)
    )
    prompt = "В каких отрисовках вызовется filterRows? Ответ — номера отрисовок с 1 через пробел."
    return Instance(prompt, " ".join(map(str, filtered_at)), {"renders": renders}, code=code)


@kind(Kind.TRACE)
def key_remount(rng: random.Random, runner: CodeRunner) -> Instance:
    ids = rng.sample(range(10, 99), 5)
    typed = {i: rng.choice(["кот", "дом", "лес", "сад", "мир", "сок", "лук"]) for i in ids}
    removed = rng.randrange(0, 4)
    key_kind = rng.choice(["index", "id"])
    remaining = [i for k, i in enumerate(ids) if k != removed]
    if key_kind == "id":
        shown = [typed[i] for i in remaining]
    else:
        # Состояние живёт по позиции: первые четыре инпута сохраняют то, что в них ввели.
        shown = [typed[ids[k]] for k in range(len(remaining))]
    code = (
        "function Row({ item }) {\n"
        "  const [text, setText] = useState('');\n"
        "  return <input value={text} onChange={e => setText(e.target.value)} />;\n"
        "}\n\n"
        "function Rows({ items }) {\n"
        "  return items.map((item, index) => "
        f"<Row key={{{'index' if key_kind == 'index' else 'item.id'}}} item={{item}} />);\n"
        "}\n"
    )
    prompt = (
        f"items — пять записей с id {', '.join(map(str, ids))}. Пользователь ввёл в инпуты по "
        f"порядку: {', '.join(typed[i] for i in ids)}. Затем из items удалили запись с id "
        f"{ids[removed]}. Что будет в инпутах сверху вниз? Ответ — слова через пробел."
    )
    params = {"ids": ids, "typed": typed, "removed": removed, "key": key_kind}
    return Instance(prompt, " ".join(shown), params, code=code)


@kind(Kind.TRACE)
def context_consumers(rng: random.Random, runner: CodeRunner) -> Instance:
    tree = [("Layout", rng.random() < 0.5, False)] + [
        (name, rng.random() < 0.5, rng.random() < 0.5)
        for name in ("Menu", "Profile", "Cart", "Search", "Footer")
    ]
    # Состояние в App: App отрисуется заново и создаст новый элемент <Layout />. Без memo Layout
    # отрисуется и потянет за собой детей без memo; потребители контекста обновятся в любом случае.
    layout_name, layout_memo, _ = tree[0]
    layout_renders = not layout_memo
    rerender = [layout_name] if layout_renders else []
    for name, memo, uses in tree[1:]:
        if uses or (layout_renders and not memo):
            rerender.append(name)
    lines = [
        "function App() {",
        "  const [theme, setTheme] = useState('light');",
        "  const value = useMemo(() => ({ theme, setTheme }), [theme]);",
        "  return <ThemeContext.Provider value={value}><Layout /></ThemeContext.Provider>;",
        "}",
        "",
    ]
    for name, memo, uses in tree:
        body = "useContext(ThemeContext); " if uses else ""
        children = "<Menu /><Profile /><Cart /><Search /><Footer />" if name == "Layout" else "…"
        wrapped = (
            f"memo(function {name}() {{ {body}return {children}; }})"
            if memo
            else f"function {name}() {{ {body}return {children}; }}"
        )
        lines.append(f"const {name} = {wrapped};")
    prompt = (
        "theme поменялся с 'light' на 'dark'. Какие компоненты (кроме App) отрисуются заново? "
        "Ответ — имена через пробел в порядке объявления; если ни один — 0."
    )
    params = {"tree": [[n, m, u] for n, m, u in tree]}
    return Instance(prompt, " ".join(rerender) or "0", params, code="\n".join(lines))


@kind(Kind.TRACE)
def stale_closure(rng: random.Random, runner: CodeRunner) -> Instance:
    ticks = rng.randint(2, 9)
    step = rng.randint(1, 5)
    start = rng.randint(0, 20)
    functional = rng.random() < 0.5
    update = f"setCount(c => c + {step})" if functional else f"setCount(count + {step})"
    code = (
        "function Timer() {\n"
        f"  const [count, setCount] = useState({start});\n"
        "  useEffect(() => {\n"
        f"    const id = setInterval(() => {update}, 1000);\n"
        "    return () => clearInterval(id);\n"
        "  }, []);\n"
        "  return <span>{count}</span>;\n"
        "}\n"
    )
    value = start + step * ticks if functional else start + step
    prompt = f"Таймер сработал {ticks} раз. Какое число покажет span? Ответ — число."
    return Instance(
        prompt,
        str(value),
        {"ticks": ticks, "step": step, "start": start, "functional": functional},
        code=code,
    )


@kind(Kind.COMPUTE)
def keyed_diff(rng: random.Random, runner: CodeRunner) -> Instance:
    old = rng.sample("ABCDEFGH", 8)
    new = [k for k in old if rng.random() < 0.75]
    added = [k for k in "IJKLMN" if rng.random() < 0.35][:3]
    for k in added:
        new.insert(rng.randint(0, len(new)), k)
    if rng.random() < 0.6 and len(new) > 2:
        i, j = rng.sample(range(len(new)), 2)
        new[i], new[j] = new[j], new[i]
    removed = [k for k in old if k not in new]
    inserted = [k for k in new if k not in old]
    kept_old_order = [k for k in old if k in new]
    kept_new_order = [k for k in new if k in old]
    # Наименьшее число перемещений = сохранённые минус длина наибольшей общей подпоследовательности
    # порядка (возрастающей по старым позициям).
    positions = [kept_old_order.index(k) for k in kept_new_order]
    lis: list[int] = []
    import bisect

    for p in positions:
        idx = bisect.bisect_left(lis, p)
        if idx == len(lis):
            lis.append(p)
        else:
            lis[idx] = p
    moves = len(positions) - len(lis)
    prompt = (
        f"Список с ключами был {' '.join(old)}, после обновления стал {' '.join(new)}. Сколько "
        "элементов при сверке по ключам удалится, сколько создастся и какое наименьшее число "
        "сохранённых элементов придётся переместить в DOM? Ответ — три числа через пробел."
    )
    answer = f"{len(removed)} {len(inserted)} {moves}"
    return Instance(prompt, answer, {"old": old, "new": new})


@kind(Kind.TRACE)
def batched_renders(rng: random.Random, runner: CodeRunner) -> Instance:
    legacy = rng.random() < 0.4
    handlers = []
    for _ in range(5):
        where = rng.choice(["onClick", "setTimeout", "fetch.then", "onClick + flushSync"])
        handlers.append((where, rng.randint(2, 3)))
    counts = []
    for where, updates in handlers:
        if where == "onClick + flushSync":
            counts.append(updates)
        elif where == "onClick":
            counts.append(1)
        else:
            # Без createRoot батчинг есть только в обработчиках событий React.
            counts.append(updates if legacy else 1)
    lines = []
    for i, (where, updates) in enumerate(handlers, 1):
        setters = [f"set{chr(64 + k)}(v => v + 1);" for k in range(1, updates + 1)]
        if where == "onClick + flushSync":
            setters = [f"flushSync(() => {s[:-1]});" for s in setters]
        lines.append(f"{i}. {where}: {' '.join(setters)}")
    root = (
        "ReactDOM.render(<App />, el) — старый API" if legacy else "createRoot(el).render(<App />)"
    )
    prompt = (
        f"React 18, приложение смонтировано через {root}. В компоненте по очереди сработали "
        "обработчики ниже. Сколько раз компонент отрисуется заново после каждого? Ответ — "
        "пять чисел через пробел."
    )
    return Instance(
        prompt,
        " ".join(map(str, counts)),
        {"legacy": legacy, "handlers": handlers},
        code="\n".join(lines),
    )
