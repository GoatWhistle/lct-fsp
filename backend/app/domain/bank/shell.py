"""Скрипты на Bash: циклы и арифметика, проверки условий, раскрытие параметров, разбиение на
слова, awk, find, режим set -e.

Bash на бэкенде не запускается: эталон считает модель на Python — узкая, ровно под конструкции
шаблона (без глобов, без IFS кроме умолчания, без локалей).
"""

import math
import random

from app.domain.bank.family import Instance
from app.domain.bank.runner import CodeRunner

PROMPT = "Что выведет скрипт? Ответ — выведенные значения через пробел по порядку."


def seq_loop(rng: random.Random, runner: CodeRunner) -> Instance:
    start, step = rng.randint(1, 9), rng.randint(2, 5)
    stop = start + step * rng.randint(3, 9) + rng.randint(0, step - 1)
    k = rng.randint(2, 7)
    code = (
        "count=0\n"
        "sum=0\n"
        f"for i in $(seq {start} {step} {stop}); do\n"
        "  count=$((count + 1))\n"
        f"  sum=$((sum + i * {k}))\n"
        "done\n"
        'echo "$count $sum"\n'
    )
    values = range(start, stop + 1, step)
    answer = f"{len(values)} {sum(v * k for v in values)}"
    return Instance(PROMPT, answer, {"start": start, "step": step, "stop": stop, "k": k}, code=code)


def test_conditions(rng: random.Random, runner: CodeRunner) -> Instance:
    a, b = rng.sample(range(2, 40), 2)
    s1, s2 = str(rng.randint(10, 99)), str(rng.randint(2, 9))
    empty = rng.choice(["", "x"])
    k = rng.randint(0, 9)
    checks = [
        ('[ "$a" -lt "$b" ] && echo 1', a < b),
        # [[ < ]] сравнивает строки посимвольно, а не как числа.
        ('[[ "$s1" < "$s2" ]] && echo 2', s1 < s2),
        ('[ -z "$v" ] && echo 3', empty == ""),
        ('[ "$a" -eq "$b" ] || echo 4', a != b),
        (f"(( a * 2 > b + {k} )) && echo 5", a * 2 > b + k),
        ('[ -n "$v" ] || echo 6', empty == ""),
        ('[ "$s1" -gt "$s2" ] && echo 7', int(s1) > int(s2)),
    ]
    picked = sorted(rng.sample(range(len(checks)), 5))
    lines = [f"a={a}", f"b={b}", f's1="{s1}"', f's2="{s2}"', f'v="{empty}"']
    lines += [checks[i][0] for i in picked]
    printed = [checks[i][0].split()[-1] for i in picked if checks[i][1]]
    prompt = (
        "Что выведет скрипт? Ответ — выведенные числа через пробел по порядку; если ничего — 0."
    )
    return Instance(
        prompt,
        " ".join(printed) or "0",
        {"a": a, "b": b, "s1": s1, "s2": s2, "v": empty, "checks": picked},
        code="\n".join(lines),
    )


def param_expansion(rng: random.Random, runner: CodeRunner) -> Instance:
    directory = rng.choice(["/var/log/app", "/srv/data/backup", "/opt/build/out", "/home/dev/tmp"])
    name = rng.choice(["report", "access", "dump", "release", "metrics"])
    stamp = rng.randint(2020, 2026) * 100 + rng.randint(1, 12)
    exts = rng.choice([["tar", "gz"], ["log", "1", "gz"], ["csv"], ["json", "bak"]])
    path = f"{directory}/{name}-{stamp}.{'.'.join(exts)}"
    base = path.rsplit("/", 1)[1]
    default = rng.choice(["none", "dev", "8080"])
    replace_from, replace_to = rng.choice([("-", "_"), (".", "-"), ("a", "A")])
    expansions = [
        ("${path##*/}", base),
        ("${path%/*}", path.rsplit("/", 1)[0]),
        ("${path%.*}", path.rsplit(".", 1)[0]),
        ("${path%%.*}", path.split(".", 1)[0]),
        ("${base#*.}", base.split(".", 1)[1]),
        ("${base##*.}", base.rsplit(".", 1)[1]),
        ("${#base}", str(len(base))),
        (f"${{missing:-{default}}}", default),
        (f"${{base//{replace_from}/{replace_to}}}", base.replace(replace_from, replace_to)),
    ]
    picked = rng.sample(expansions, 4)
    lines = [f'path="{path}"', 'base="${path##*/}"']
    lines += [f'echo "{expr}"' for expr, _ in picked]
    return Instance(
        PROMPT,
        " ".join(value for _, value in picked),
        {"path": path, "expansions": [expr for expr, _ in picked]},
        code="\n".join(lines),
    )


def word_splitting(rng: random.Random, runner: CodeRunner) -> Instance:
    words = rng.sample(["alpha", "beta", "gamma", "delta", "omega", "sigma"], rng.randint(2, 4))
    # Двойной пробел внутри строки: при разбиении на слова пустых аргументов не получается.
    files = "  ".join(words[:2]) + "".join(f" {w}" for w in words[2:])
    quoted = rng.sample(["x y", "a b c", "p q"], rng.randint(1, 2))
    plain = rng.sample(["k", "m", "n", "z"], rng.randint(1, 2))
    args = quoted + plain
    rng.shuffle(args)
    split_count = sum(len(a.split()) for a in args)
    calls = [
        ("count $files", len(files.split())),
        ('count "$files"', 1),
        ('count "$@"', len(args)),
        ("count $@", split_count),
        ('count "$*"', 1),
        ('count "${arr[@]}"', len(args)),
        ("count ${arr[@]}", split_count),
        ('count "${arr[*]}"', 1),
    ]
    picked = sorted(rng.sample(range(len(calls)), 5))
    set_args = " ".join(f'"{a}"' if " " in a else a for a in args)
    lines = [
        "count() { echo $#; }",
        f'files="{files}"',
        f"set -- {set_args}",
        f"arr=({set_args})",
    ]
    lines += [calls[i][0] for i in picked]
    return Instance(
        PROMPT,
        " ".join(str(calls[i][1]) for i in picked),
        {"files": files, "args": args, "calls": picked},
        code="\n".join(lines),
    )


def awk_sum(rng: random.Random, runner: CodeRunner) -> Instance:
    regions = rng.sample(["north", "south", "east", "west", "center"], rng.randint(3, 4))
    rows = [
        (rng.choice(regions), rng.choice(["apple", "pear", "plum"]), rng.randint(1, 30))
        for _ in range(rng.randint(7, 10))
    ]
    threshold = rng.randint(5, 15)
    totals: dict[str, int] = {}
    for region, _, qty in rows:
        if qty > threshold:
            totals[region] = totals.get(region, 0) + qty
    lines = ["$ cat sales.csv", *(f"{r},{f},{q}" for r, f, q in rows), ""]
    lines.append(
        f"$ awk -F, '$3 > {threshold} {{ s[$1] += $3 }} END {{ for (k in s) print k, s[k] }}' "
        "sales.csv | sort"
    )
    prompt = (
        "Что выведет последняя команда? Ответ — пары «регион сумма» через пробел, как в выводе; "
        "если вывода нет — 0."
    )
    answer = " ".join(f"{k} {totals[k]}" for k in sorted(totals)) or "0"
    return Instance(prompt, answer, {"rows": rows, "threshold": threshold}, code="\n".join(lines))


def find_filters(rng: random.Random, runner: CodeRunner) -> Instance:
    days, size = rng.randint(3, 10), rng.randint(1, 2)
    pattern = rng.choice(["*.log", "app*", "*.gz"])
    stems = rng.sample(["api", "db", "audit", "cron", "auth", "nginx", "worker", "mail"], 6)
    suffixes = [".log", ".log.1.gz", ".gz", ".txt"]
    files = []
    for stem in stems:
        # Чаще — имя под шаблон: иначе ответ почти всегда «0».
        suffix = rng.choice(suffixes)
        if rng.random() < 0.7:
            if pattern == "app*":
                stem = "app-" + stem
            else:
                suffix = rng.choice([x for x in suffixes if x.endswith(pattern[1:])])
        name = stem + suffix
        # Возраст — целые сутки плюс часы: -mtime +N отбрасывает дробную часть суток.
        age_days, age_hours = rng.randint(days - 1, days + 5), rng.randint(0, 23)
        kib = rng.choice([900, 1024, 1500, 2048, 3000, 5000, 9000, 20000])
        files.append((name, age_days, age_hours, kib))

    def matches(name: str, age_days: int, kib: int) -> bool:
        glob_ok = (
            name.endswith(pattern[1:]) if pattern.startswith("*") else name.startswith(pattern[:-1])
        )
        # -size +NM: размер в мебибайтах с округлением вверх строго больше N.
        return glob_ok and age_days > days and math.ceil(kib / 1024) > size

    found = [name for name, d, _, kib in files if matches(name, d, kib)]
    lines = [f"{name}: изменён {d} сут {h} ч назад, {kib} КиБ" for name, d, h, kib in files]
    prompt = (
        f"Какие файлы из /var/log найдёт find /var/log -name '{pattern}' -mtime +{days} "
        f"-size +{size}M? Ответ — имена через пробел в порядке списка; если ни одного — 0."
    )
    return Instance(
        prompt,
        " ".join(found) or "0",
        {"files": files, "days": days, "size": size, "pattern": pattern},
        code="\n".join(lines),
    )


# Команда и что она делает под set -e: печатает, ничего, завершает скрипт, завершает только
# с pipefail.
_STATEMENTS = [
    ("false || echo {x}", "echo"),
    ("false && echo {x}", "skip"),
    ("true | false", "fail"),
    ("false | true", "pipefail"),
    ("if false; then echo {x}; fi", "skip"),
    ("x=$(false)", "fail"),
    ("i=0; (( i++ ))", "fail"),
    ("i=1; (( i++ ))", "skip"),
    ("grep -q zzz /dev/null || true", "skip"),
]


def errexit(rng: random.Random, runner: CodeRunner) -> Instance:
    pipefail = rng.random() < 0.5
    letters = iter(rng.sample("ABCDEFGHKMNPRSTUVWXZ", 11))
    lines = ["set -e" + (" -o pipefail" if pipefail else "")]
    printed: list[str] = []
    status = 0
    stopped = False
    for statement, effect in rng.sample(_STATEMENTS, 5):
        echo = next(letters)
        lines.append(f"echo {echo}")
        if not stopped:
            printed.append(echo)
        x = next(letters)
        lines.append(statement.format(x=x))
        if stopped:
            continue
        if effect == "echo":
            printed.append(x)
        elif effect == "fail" or (effect == "pipefail" and pipefail):
            stopped, status = True, 1
    last = next(letters)
    lines.append(f"echo {last}")
    if not stopped:
        printed.append(last)
    prompt = (
        "Скрипт запущен через bash script.sh. Что он выведет и с каким кодом завершится? Ответ — "
        "выведенные буквы и код через пробел."
    )
    return Instance(
        prompt,
        " ".join([*printed, str(status)]),
        {"pipefail": pipefail, "lines": lines},
        code="\n".join(lines),
    )
