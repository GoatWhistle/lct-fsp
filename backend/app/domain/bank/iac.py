"""Инфраструктура как код: план Terraform, count и for_each, приоритет переменных, cidrsubnet,
выражения HCL, moved и removed, идемпотентность и циклы Ansible, serial и forks."""

import ipaddress
import math
import random

from app.domain.bank.family import Instance
from app.domain.bank.runner import CodeRunner

_RESOURCES = [
    'aws_instance.web["a"]',
    "aws_instance.worker[0]",
    "aws_s3_bucket.logs",
    "aws_db_instance.main",
    "aws_security_group.app",
    "aws_eip.nat[1]",
    "aws_iam_role.deploy",
    "data.aws_ami.ubuntu",
    "aws_route53_record.api",
    "aws_lb.public",
]


def plan_symbols(rng: random.Random, runner: CodeRunner) -> Instance:
    rows = []
    for address in rng.sample(_RESOURCES, rng.randint(5, 8)):
        symbol = "<=" if address.startswith("data.") else rng.choice(["+", "~", "-", "-/+", "+/-"])
        rows.append((symbol, address))
    add = sum(1 for s, _ in rows if s in ("+", "-/+", "+/-"))
    change = sum(1 for s, _ in rows if s == "~")
    destroy = sum(1 for s, _ in rows if s in ("-", "-/+", "+/-"))
    lines = [f"{symbol:>3} {address}" for symbol, address in rows]
    prompt = (
        "Фрагмент вывода terraform plan ниже. Что Terraform напишет в итоговой строке «Plan: X "
        "to add, Y to change, Z to destroy»? Ответ — три числа через пробел."
    )
    return Instance(prompt, f"{add} {change} {destroy}", {"rows": rows}, code="\n".join(lines))


def resource_count(rng: random.Random, runner: CodeRunner) -> Instance:
    web = rng.randint(1, 5)
    zones = rng.sample(["a", "b", "c", "d"], rng.randint(2, 4))
    buckets = rng.choices(["app", "audit", "billing"], k=rng.randint(3, 5))
    users = rng.sample(["anna", "oleg", "ira", "max"], rng.randint(1, 4))
    nat = rng.random() < 0.5
    nat_count = rng.randint(1, 3)
    zone_list = ", ".join(f'"{z}"' for z in zones)
    bucket_list = ", ".join(f'"{b}"' for b in buckets)
    user_map = ", ".join(f'{u} = "dev"' for u in users)
    code = (
        f'variable "zones"      {{ default = [{zone_list}] }}\n'
        f'variable "enable_nat" {{ default = {str(nat).lower()} }}\n\n'
        f'resource "aws_instance" "web"      {{ count = {web} }}\n'
        'resource "aws_subnet" "private"    { count = length(var.zones) }\n'
        f'resource "aws_s3_bucket" "logs"    {{ for_each = toset([{bucket_list}]) }}\n'
        f'resource "aws_iam_user" "dev"      {{ for_each = {{ {user_map} }} }}\n'
        f'resource "aws_eip" "nat"           {{ count = var.enable_nat ? {nat_count} : 0 }}'
    )
    keyed = len(set(buckets)) + len(users)
    total = web + len(zones) + keyed + (nat_count if nat else 0)
    prompt = (
        "Сколько экземпляров ресурсов создаст terraform apply на пустом состоянии и сколько из "
        "них будут с ключом-строкой в адресе? Атрибуты ресурсов опущены. Ответ — два числа через "
        "пробел."
    )
    params = {
        "web": web,
        "zones": zones,
        "buckets": buckets,
        "users": users,
        "nat": nat,
        "nat_count": nat_count,
    }
    return Instance(prompt, f"{total} {keyed}", params, code=code)


_VALUES = {
    "region": ["eu-north", "eu-west", "ru-central", "us-east", "ap-south", "me-west", "sa-east"],
    "size": ["nano", "micro", "small", "medium", "large", "xlarge", "metal"],
    "env": ["dev", "test", "stage", "prod", "demo", "perf", "lab"],
}


def var_precedence(rng: random.Random, runner: CodeRunner) -> Instance:
    names = list(_VALUES)
    pools = {name: rng.sample(_VALUES[name], 7) for name in names}
    # Источники от слабого к сильному; у CLI порядок флагов задан командой.
    sources = ["default", "env", "terraform.tfvars", "a.auto.tfvars", "z.auto.tfvars"]
    defined: dict[str, dict[str, str]] = {name: {} for name in names}
    for name in names:
        for i, source in enumerate(sources):
            if source == "default" or rng.random() < 0.45:
                defined[name][source] = pools[name][i]
    # Флаги CLI по порядку: -var задаёт одну переменную, -var-file — все из prod.tfvars.
    prod = {n: pools[n][6] for n in rng.sample(names, rng.randint(1, 2))}
    cli: list[tuple[str, str, str]] = []
    for _ in range(rng.randint(0, 2)):
        name = rng.choice(names)
        cli.append(("-var", name, pools[name][5]))
    if rng.random() < 0.6:
        cli.insert(rng.randint(0, len(cli)), ("-var-file", "", ""))
    final = {}
    for name in names:
        value = ""
        for source in sources:
            value = defined[name].get(source, value)
        for flag, var, cli_value in cli:
            if flag == "-var" and var == name:
                value = cli_value
            elif flag == "-var-file" and name in prod:
                value = prod[name]
        final[name] = value
    lines = ["# variables.tf"]
    lines += [f'variable "{n}" {{ default = "{defined[n]["default"]}" }}' for n in names]
    env = [f"TF_VAR_{n}={defined[n]['env']}" for n in names if "env" in defined[n]]
    lines += ["", "# окружение", *(env or ["(переменных TF_VAR_ нет)"])]
    for source in sources[2:]:
        body = [f'{n} = "{defined[n][source]}"' for n in names if source in defined[n]]
        if body:
            lines += ["", f"# {source}", *body]
    if any(flag == "-var-file" for flag, _, _ in cli):
        lines += ["", "# prod.tfvars", *(f'{v} = "{value}"' for v, value in prod.items())]
    command = "terraform apply" + "".join(
        " -var-file=prod.tfvars" if flag == "-var-file" else f" -var '{var}={value}'"
        for flag, var, value in cli
    )
    lines += ["", f"$ {command}"]
    prompt = (
        "Какие значения получат переменные region, size и env? Ответ — три значения через пробел "
        "в этом порядке."
    )
    return Instance(
        prompt,
        " ".join(final[n] for n in names),
        {"defined": defined, "cli": cli, "prod": prod},
        code="\n".join(lines),
    )


def cidrsubnet(rng: random.Random, runner: CodeRunner) -> Instance:
    base = ipaddress.IPv4Network(
        f"10.{rng.randint(0, 255)}.0.0/{rng.choice([16, 16, 20])}", strict=False
    )
    calls = []
    results = []
    for _ in range(2):
        newbits = rng.randint(2, 8)
        netnum = rng.randrange(2**newbits)
        subnet = list(base.subnets(new_prefix=base.prefixlen + newbits))[netnum]
        calls.append(f'cidrsubnet("{base}", {newbits}, {netnum})')
        results.append(str(subnet))
    newbits = rng.randint(4, 8)
    netnum = rng.randrange(2**newbits)
    subnet = list(base.subnets(new_prefix=base.prefixlen + newbits))[netnum]
    hostnum = rng.choice([1, 5, 10, -2, -1])
    # Отрицательный номер хоста считается с конца сети: -1 — последний адрес.
    host = subnet.network_address + (hostnum if hostnum >= 0 else subnet.num_addresses + hostnum)
    calls.append(f'cidrhost(cidrsubnet("{base}", {newbits}, {netnum}), {hostnum})')
    results.append(str(host))
    prompt = (
        "Что вернут функции Terraform? Ответ — три значения через пробел по порядку, подсети — "
        "в записи CIDR."
    )
    return Instance(prompt, " ".join(results), {"calls": calls}, code="\n".join(calls))


def count_vs_for_each(rng: random.Random, runner: CodeRunner) -> Instance:
    pool = ["alpha", "beta", "gamma", "delta", "omega", "sigma", "kappa", "theta", "zeta"]
    names = rng.sample(pool, rng.randint(4, 7))
    replace = rng.random() < 0.5
    after = list(names)
    edits = []
    for _ in range(rng.randint(1, 2)):
        if rng.random() < 0.5 and len(after) > 3:
            gone = after.pop(rng.randrange(len(after) - 1))
            edits.append(f'убрали "{gone}"')
        else:
            extra = next(x for x in pool if x not in after and x not in names)
            k = rng.randrange(len(after) + 1)
            after.insert(k, extra)
            edits.append(f'вставили "{extra}" на место {k + 1}')
    # count: экземпляр i — i-й элемент списка; for_each: экземпляр — сам элемент.
    common = min(len(names), len(after))
    shifted = sum(1 for i in range(common) if names[i] != after[i])
    grown = max(0, len(after) - len(names))
    shrunk = max(0, len(names) - len(after))
    # Сдвинутый экземпляр меняется на месте или пересоздаётся.
    count_plan = (shifted + grown, 0, shifted + shrunk) if replace else (grown, shifted, shrunk)
    each_plan = (len(set(after) - set(names)), 0, len(set(names) - set(after)))
    what = "в списке " + ", затем ".join(edits)
    attribute = "bucket" if replace else "тега Name"
    resource = "aws_s3_bucket" if replace else "aws_instance"
    effect = "требует пересоздания ресурса" if replace else "применяется на месте"

    def body(value: str) -> str:
        return f"  bucket = {value}\n" if replace else f"  tags = {{ Name = {value} }}\n"

    code = (
        f"# было: names = {names}\n# стало: names = {after}\n\n"
        f'resource "{resource}" "by_count" {{\n'
        "  count = length(var.names)\n" + body("var.names[count.index]") + "}\n\n"
        f'resource "{resource}" "by_key" {{\n'
        "  for_each = toset(var.names)\n" + body("each.key") + "}"
    ).replace("'", '"')
    prompt = (
        f"Оба ресурса уже применены. Затем {what}. Смена {attribute} {effect}. Что покажет "
        "terraform plan для by_count и для by_key? Ответ — шесть чисел через пробел: add, "
        "change, destroy для by_count, затем для by_key."
    )
    return Instance(
        prompt,
        " ".join(map(str, (*count_plan, *each_plan))),
        {"names": names, "after": after, "replace": replace},
        code=code,
    )


def tf_expressions(rng: random.Random, runner: CodeRunner) -> Instance:
    services = rng.sample(["api", "web", "db", "cache", "queue", "auth"], rng.randint(3, 5))
    sizes = {s: rng.randint(1, 9) for s in services}
    threshold = rng.randint(2, max(sizes.values()))
    zones = rng.choices(["a", "b", "c", "d"], k=rng.randint(3, 6))
    envs = rng.sample(["dev", "stage", "prod"], rng.randint(1, 3))
    big = {k: v for k, v in sizes.items() if v >= threshold}
    size_map = ", ".join(f"{k} = {v}" for k, v in sizes.items())
    code = (
        f'variable "sizes" {{ default = {{ {size_map} }} }}\n'
        f'variable "zones" {{ default = [{", ".join(f"{z!r}" for z in zones)}] }}\n'
        f'variable "envs"  {{ default = [{", ".join(f"{e!r}" for e in envs)}] }}\n\n'
        "locals {\n"
        f"  big   = {{ for k, v in var.sizes : k => v if v >= {threshold} }}\n"
        "  zones = toset(var.zones)\n"
        "  pairs = setproduct(var.envs, local.zones)\n"
        "}\n\n"
        'output "a" { value = length(local.big) }\n'
        'output "b" { value = sum(values(local.big)) }\n'
        'output "c" { value = length(local.zones) }\n'
        'output "d" { value = length(local.pairs) }'
    ).replace("'", '"')
    answer = f"{len(big)} {sum(big.values())} {len(set(zones))} {len(envs) * len(set(zones))}"
    prompt = "Какие значения выведут outputs a, b, c и d? Ответ — четыре числа через пробел."
    params = {"sizes": sizes, "threshold": threshold, "zones": zones, "envs": envs}
    return Instance(prompt, answer, params, code=code)


def moved_refactor(rng: random.Random, runner: CodeRunner) -> Instance:
    web = rng.randint(2, 8)
    module_size = rng.randint(2, 12)
    steps = rng.sample(
        ["rename", "for_each", "module", "grow", "remove", "replace"], rng.randint(2, 4)
    )
    if "for_each" in steps and "grow" in steps:
        steps.remove("grow")
    add = destroy = 0
    lines = [
        "Было в состоянии:",
        f"  aws_instance.web[0] … aws_instance.web[{web - 1}]  (count = {web})",
        "  aws_s3_bucket.logs",
        f"  module.net — {module_size} ресурсов внутри",
        "  aws_eip.old",
        "  aws_lb.public",
        "",
        "Правки конфигурации и запуск:",
    ]
    for step in steps:
        moved = rng.random() < 0.5
        note = "с блоком moved" if moved else "без блока moved"
        if step == "rename":
            lines.append(f"- aws_s3_bucket.logs переименован в aws_s3_bucket.audit, {note}")
            if not moved:
                add, destroy = add + 1, destroy + 1
        elif step == "for_each":
            lines.append(
                f"- web переведён с count = {web} на for_each по {web} именам, "
                + ("moved для каждого экземпляра" if moved else "без блоков moved")
            )
            if not moved:
                add, destroy = add + web, destroy + web
        elif step == "module":
            lines.append(f"- module.net переименован в module.network, {note}")
            if not moved:
                add, destroy = add + module_size, destroy + module_size
        elif step == "grow":
            extra = rng.randint(1, 5)
            lines.append(f"- у web count увеличен с {web} до {web + extra}")
            add += extra
        elif step == "replace":
            lines.append("- plan запускают с -replace=aws_lb.public")
            add, destroy = add + 1, destroy + 1
        else:
            keep = rng.random() < 0.5
            if keep:
                lines.append(
                    "- ресурс aws_eip.old убран из кода, добавлен блок removed с lifecycle "
                    "{ destroy = false }"
                )
            else:
                lines.append("- ресурс aws_eip.old убран из кода")
                destroy += 1
    prompt = (
        "Что покажет terraform plan после всех правок? Атрибуты ресурсов не менялись. Ответ — "
        "два числа через пробел: сколько to add и сколько to destroy."
    )
    return Instance(prompt, f"{add} {destroy}", {"lines": lines}, code="\n".join(lines))


# Задача, changed в первом прогоне на чистом сервере, changed во втором.
_TASKS = [
    ("apt: name=nginx state=present", True, False),
    ("copy: src=nginx.conf dest=/etc/nginx/nginx.conf", True, False),
    ("lineinfile: path=/etc/hosts line='10.0.0.5 db'", True, False),
    ("user: name=deploy", True, False),
    ("file: path=/opt/app state=directory", True, False),
    ("template: src=app.env.j2 dest=/opt/app/.env", True, False),
    ("command: /opt/app/migrate.sh", True, True),
    ("command: /opt/app/init.sh creates=/opt/app/.initialized", True, False),
    ("shell: date > /tmp/last-deploy", True, True),
    ("shell: cat /etc/os-release  # changed_when: false", False, False),
    ("command: nginx -t  # changed_when: false", False, False),
    ("service: name=nginx state=restarted", True, True),
    ("service: name=nginx state=reloaded", True, True),
]


def ansible_idempotency(rng: random.Random, runner: CodeRunner) -> Instance:
    tasks = [_TASKS[0], *rng.sample(_TASKS[1:], rng.randint(4, 8))]
    notifying = {i for i in range(len(tasks)) if rng.random() < 0.35}
    first = sum(1 for _, changed, _ in tasks if changed)
    second = sum(1 for _, _, again in tasks if again)
    handler = int(any(tasks[i][1] for i in notifying)) + int(any(tasks[i][2] for i in notifying))
    lines = [
        f"{i}. {text}" + ("  # notify: restart nginx" if i - 1 in notifying else "")
        for i, (text, _, _) in enumerate(tasks, 1)
    ]
    prompt = (
        "Плейбук запускают дважды подряд на чистом сервере. Наш nginx.conf отличается от "
        "стандартного, init.sh создаёт /opt/app/.initialized, остальные скрипты ничего не "
        "проверяют. Сколько задач (без обработчиков) отчитаются changed в первом и во втором "
        "прогоне и сколько раз всего выполнится обработчик restart nginx? Ответ — три числа "
        "через пробел."
    )
    return Instance(
        prompt,
        f"{first} {second} {handler}",
        {"tasks": [t for t, _, _ in tasks], "notifying": sorted(notifying)},
        code="\n".join(lines),
    )


def loop_when(rng: random.Random, runner: CodeRunner) -> Instance:
    names = rng.sample(["anna", "oleg", "ira", "max", "lev", "zoya", "egor"], rng.randint(5, 7))
    users = []
    for name in names:
        active = rng.random() < 0.7
        role = rng.choice(["admin", "dev", "dev", "guest"])
        exists = rng.random() < 0.4
        users.append((name, active, role, exists))
    skipped = changed = ok = 0
    for _, active, role, exists in users:
        if not active or role == "guest":
            skipped += 1
        elif exists:
            ok += 1
        else:
            changed += 1
    lines = [
        "- name: создать пользователей",
        "  user: name={{ item.name }} state=present",
        '  loop: "{{ users }}"',
        "  when: item.active and item.role != 'guest'",
        "",
        "users:",
    ]
    lines += [
        f"  - {{name: {n}, active: {str(a).lower()}, role: {r}}}"
        + ("  # уже есть на сервере" if e else "")
        for n, a, r, e in users
    ]
    prompt = (
        "Сколько итераций цикла будет пропущено (skipped), сколько изменят систему (changed) и "
        "сколько пройдут без изменений (ok)? Ответ — три числа через пробел."
    )
    return Instance(prompt, f"{skipped} {changed} {ok}", {"users": users}, code="\n".join(lines))


def ansible_serial(rng: random.Random, runner: CodeRunner) -> Instance:
    hosts = rng.randint(6, 20)
    forks = rng.choice([2, 3, 5, 10])
    durations = [rng.randint(1, 9) * 10 for _ in range(rng.randint(2, 4))]
    if rng.random() < 0.5:
        percent = rng.choice([20, 25, 30, 40, 50])
        serial_text = f'"{percent}%"'
        # Процент в serial округляется вниз, но не меньше одного хоста.
        serial = max(1, math.floor(hosts * percent / 100))
    else:
        serial = rng.randint(2, hosts - 1)
        serial_text = str(serial)

    def play(batch: int) -> int:
        return sum(math.ceil(batch / forks) * d for d in durations)

    plain = play(hosts)
    batches = [serial] * (hosts // serial) + ([hosts % serial] if hosts % serial else [])
    with_serial = sum(play(b) for b in batches)
    prompt = (
        f"Плей на {hosts} хостов, forks = {forks}, стратегия linear: задача выполняется на "
        "хостах волнами по forks штук, следующая задача — когда предыдущая закончилась на всех "
        f"хостах пачки. Задачи длятся {', '.join(map(str, durations))} с на каждом хосте. "
        f"Сколько секунд займёт плей без serial и с serial: {serial_text}? Ответ — два числа "
        "через пробел."
    )
    return Instance(
        prompt,
        f"{plain} {with_serial}",
        {"hosts": hosts, "forks": forks, "durations": durations, "serial": serial_text},
    )


# От слабого к сильному, как в документации Ansible (выборка уровней).
_ANSIBLE_SOURCES = [
    "roles/app/defaults/main.yml",
    "group_vars/all.yml",
    "group_vars/web.yml",
    "host_vars/web-1.yml",
    "vars в плее",
    "roles/app/vars/main.yml",
    "-e в командной строке",
]


def ansible_vars(rng: random.Random, runner: CodeRunner) -> Instance:
    names = ["app_port", "log_level", "workers"]
    pools: dict[str, list[object]] = {
        "app_port": rng.sample(range(8000, 8100), 7),
        "log_level": rng.sample(["debug", "info", "warn", "error", "trace", "fatal", "notice"], 7),
        "workers": rng.sample(range(1, 33), 7),
    }
    defined: dict[str, dict[str, object]] = {}
    for name in names:
        defined[name] = {}
        for i, source in enumerate(_ANSIBLE_SOURCES):
            if i == 0 or rng.random() < 0.35:
                defined[name][source] = pools[name][i]
    final = {}
    for name in names:
        for source in _ANSIBLE_SOURCES:
            if source in defined[name]:
                final[name] = defined[name][source]
    lines = []
    for source in _ANSIBLE_SOURCES:
        body = [f"{n}: {defined[n][source]}" for n in names if source in defined[n]]
        if body:
            lines += [f"# {source}", *body, ""]
    prompt = (
        "Хост web-1 входит в группу web. Плей с ролью app выполняется на нём, переменные заданы "
        "в местах ниже. Какие значения получат app_port, log_level и workers? Ответ — три значения "
        "через пробел в этом порядке."
    )
    return Instance(
        prompt,
        " ".join(str(final[n]) for n in names),
        {"defined": defined},
        code="\n".join(lines).strip(),
    )
