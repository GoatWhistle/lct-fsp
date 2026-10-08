"""Linux и сети: права файлов, umask, навигация, коды возврата, подсети и маршруты, правила
межсетевого экрана, конвейеры текстовых утилит, рукопожатия TCP и TLS."""

import ipaddress
import posixpath
import random
from collections import Counter

from app.domain.bank.family import Instance, Kind, kind
from app.domain.bank.runner import CodeRunner

RWX = "rwx"


def _symbolic(mode: int) -> str:
    return "".join(
        RWX[i] if mode & (1 << (8 - (k * 3 + i))) else "-" for k in range(3) for i in range(3)
    )


@kind(Kind.COMPUTE)
def chmod_modes(rng: random.Random, runner: CodeRunner) -> Instance:
    modes = [rng.randrange(0, 0o1000) for _ in range(3)]
    to_octal = rng.random() < 0.5
    if to_octal:
        listing = ", ".join(_symbolic(m) for m in modes)
        prompt = (
            f"Права файлов в выводе ls -l: {listing}. Запишите их в восьмеричном виде, как для "
            "chmod. Ответ — три числа через пробел, каждое из трёх цифр."
        )
        answer = " ".join(f"{m:03o}" for m in modes)
    else:
        listing = ", ".join(f"{m:03o}" for m in modes)
        prompt = (
            f"Права заданы chmod {listing}. Как они выглядят в выводе ls -l (девять символов "
            "rwx)? Ответ — три строки через пробел."
        )
        answer = " ".join(_symbolic(m) for m in modes)
    return Instance(prompt, answer, {"modes": modes, "to_octal": to_octal})


@kind(Kind.TRACE)
def path_navigation(rng: random.Random, runner: CodeRunner) -> Instance:
    dirs = ["etc", "var", "log", "nginx", "app", "srv", "data", "home", "user", "tmp"]
    cwd = "/" + "/".join(rng.sample(dirs, rng.randint(1, 3)))
    commands = []
    for _ in range(4):
        commands.append(
            rng.choice(
                [
                    f"cd {rng.choice(dirs)}",
                    "cd ..",
                    f"cd ../{rng.choice(dirs)}",
                    f"cd /{rng.choice(dirs)}",
                    "cd .",
                    f"cd {rng.choice(dirs)}/../{rng.choice(dirs)}",
                ]
            )
        )
    path = cwd
    for cmd in commands:
        target = cmd.split(" ", 1)[1]
        path = posixpath.normpath(posixpath.join(path, target))
    prompt = (
        f"Текущий каталог — {cwd}, все упомянутые каталоги существуют. Какой каталог выведет "
        "pwd после команд? Ответ — абсолютный путь."
    )
    return Instance(
        prompt, path, {"cwd": cwd, "commands": commands}, code="\n".join([*commands, "pwd"])
    )


@kind(Kind.COMPUTE)
def umask_perms(rng: random.Random, runner: CodeRunner) -> Instance:
    umask = rng.choice([0, 2]) * 64 + rng.choice([0, 2, 3, 5, 7]) * 8 + rng.choice([0, 2, 5, 6, 7])
    mode = rng.choice([0o600, 0o640, 0o644, 0o700, 0o750, 0o755, 0o775])
    file_mode = 0o666 & ~umask
    dir_mode = 0o777 & ~umask
    prompt = (
        f"umask = {umask:04o}. С какими правами (восьмерично) touch создаст файл, mkdir — "
        f"каталог, а install -m {mode:o} — файл? Ответ — три трёхзначных числа через пробел."
    )
    # install -m задаёт права явно: umask на них не действует.
    answer = f"{file_mode:03o} {dir_mode:03o} {mode:03o}"
    return Instance(prompt, answer, {"umask": umask, "mode": mode})


@kind(Kind.COMPUTE)
def cidr_hosts(rng: random.Random, runner: CodeRunner) -> Instance:
    prefix = rng.randint(20, 30)
    address = ipaddress.IPv4Address(rng.randint(0x0A000000, 0x0AFFFFFF))
    net = ipaddress.IPv4Network(f"{address}/{prefix}", strict=False)
    hosts = net.num_addresses - 2
    prompt = (
        f"Адрес {address}/{prefix}. Каковы адрес сети, широковещательный адрес и число адресов "
        "для хостов? Ответ — три значения через пробел."
    )
    return Instance(
        prompt,
        f"{net.network_address} {net.broadcast_address} {hosts}",
        {"address": str(address), "prefix": prefix},
    )


@kind(Kind.TRACE)
def exit_chain(rng: random.Random, runner: CodeRunner) -> Instance:
    names = "abcdef"[: rng.randint(5, 6)]
    cmds = [(name, rng.choice([0, 0, 1, 2, 127])) for name in names]
    ops = [rng.choice(["&&", "||", ";"]) for _ in range(len(cmds) - 1)]
    ran = []
    status = 0
    for i, (name, code) in enumerate(cmds):
        run = i == 0 or (
            ops[i - 1] == ";"
            or (ops[i - 1] == "&&" and status == 0)
            or (ops[i - 1] == "||" and status != 0)
        )
        if run:
            ran.append(name)
            status = code
    line = cmds[0][0] + "".join(
        f" {op} {name}" for op, (name, _) in zip(ops, cmds[1:], strict=True)
    )
    codes = ", ".join(f"{n} завершается с кодом {c}" for n, c in cmds)
    prompt = (
        f"Команды: {codes}. Какие из них выполнит строка ниже и каким будет $? в конце? Ответ — "
        "имена выполненных команд и код через пробел."
    )
    return Instance(prompt, " ".join([*ran, str(status)]), {"cmds": cmds, "ops": ops}, code=line)


@kind(Kind.COMPUTE)
def subnet_membership(rng: random.Random, runner: CodeRunner) -> Instance:
    prefix = rng.randint(22, 28)
    base = ipaddress.IPv4Address(rng.randint(0xC0A80000, 0xC0A8FFFF))
    net = ipaddress.IPv4Network(f"{base}/{prefix}", strict=False)
    candidates = []
    for _ in range(5):
        if rng.random() < 0.5:
            ip = net.network_address + rng.randrange(net.num_addresses)
        else:
            ip = net.network_address + rng.randint(-600, net.num_addresses + 600)
        candidates.append(ipaddress.IPv4Address(ip))
    answers = ["да" if ip in net else "нет" for ip in candidates]
    prompt = (
        f"Подсеть {net}. Какие адреса ей принадлежат? Ответ — «да» или «нет» для каждого адреса "
        "через пробел по порядку."
    )
    return Instance(
        prompt,
        " ".join(answers),
        {"net": str(net), "ips": [str(ip) for ip in candidates]},
        code="\n".join(map(str, candidates)),
    )


@kind(Kind.TRACE)
def sort_uniq(rng: random.Random, runner: CodeRunner) -> Instance:
    ips = [f"10.0.0.{rng.randint(1, 9)}" for _ in range(rng.randint(10, 14))]
    counts = Counter(ips)
    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:2]
    code = (
        "$ cat access.log | cut -d' ' -f1\n"
        + "\n".join(ips)
        + ("\n\n$ cut -d' ' -f1 access.log | sort | uniq -c | sort -k1,1nr -k2,2 | head -2")
    )
    prompt = (
        "Что выведет последняя команда? Ответ — пары «число адрес» через пробел, как в выводе, "
        "без отступов."
    )
    answer = " ".join(f"{n} {ip}" for ip, n in top)
    return Instance(prompt, answer, {"ips": ips}, code=code)


@kind(Kind.TRACE)
def firewall_rules(rng: random.Random, runner: CodeRunner) -> Instance:
    sources = ["10.0.0.0/8", "192.168.0.0/16", "0.0.0.0/0", "10.1.0.0/16"]
    policy = rng.choice(["DROP", "ACCEPT"])
    other = "ACCEPT" if policy == "DROP" else "DROP"
    rules = []
    for _ in range(rng.randint(4, 6)):
        rules.append(
            (
                rng.choice([other, other, policy]),
                rng.choice(["tcp", "tcp", "udp"]),
                rng.choice([22, 80, 443, 53]),
                rng.choice(sources),
            )
        )
    packets = []
    for _ in range(6):
        # Чаще — пакеты под порт и протокол какого-то правила: иначе почти всё уходит в политику.
        if rng.random() < 0.75:
            _, proto, port, _ = rng.choice(rules)
        else:
            proto, port = rng.choice(["tcp", "udp"]), rng.choice([22, 80, 443, 53, 8080])
        src = rng.choice(["10.1.2.3", "10.9.0.7", "192.168.1.5", "8.8.8.8"])
        packets.append((proto, port, src))
    verdicts = []
    for proto, port, src in packets:
        verdict = policy
        for action, rproto, rport, rsrc in rules:
            if (
                proto == rproto
                and port == rport
                and ipaddress.IPv4Address(src) in ipaddress.IPv4Network(rsrc)
            ):
                verdict = action
                break
        verdicts.append(verdict)
    lines = [f"-A INPUT -p {p} --dport {port} -s {src} -j {a}" for a, p, port, src in rules]
    pkts = "; ".join(f"{p}/{port} от {src}" for p, port, src in packets)
    prompt = (
        f"Цепочка INPUT с политикой по умолчанию {policy} и правилами ниже (срабатывает первое "
        f"подходящее). Что будет с пакетами: {pkts}? Ответ — ACCEPT или DROP для каждого через "
        "пробел."
    )
    return Instance(
        prompt,
        " ".join(verdicts),
        {"rules": rules, "policy": policy, "packets": packets},
        code="\n".join(lines),
    )


@kind(Kind.TRACE)
def longest_prefix(rng: random.Random, runner: CodeRunner) -> Instance:
    routes = [
        ("0.0.0.0/0", "gw-default"),
        (f"10.{rng.randint(0, 3)}.0.0/16", "gw-a"),
        (f"10.{rng.randint(0, 3)}.{rng.randint(0, 3)}.0/24", "gw-b"),
        ("10.0.0.0/8", "gw-c"),
        (f"10.{rng.randint(0, 3)}.{rng.randint(0, 3)}.128/25", "gw-d"),
        (f"10.{rng.randint(0, 3)}.0.0/{rng.choice([12, 14])}", "gw-e"),
    ]
    rng.shuffle(routes)
    networks = [(ipaddress.IPv4Network(r, strict=False), gw) for r, gw in routes]
    ips = []
    for _ in range(5):
        if rng.random() < 0.85:
            ips.append(
                ipaddress.IPv4Address(
                    f"10.{rng.randint(0, 3)}.{rng.randint(0, 3)}.{rng.randint(0, 255)}"
                )
            )
        else:
            ips.append(ipaddress.IPv4Address(f"172.16.{rng.randint(0, 9)}.{rng.randint(1, 254)}"))
    hops = []
    for ip in ips:
        best = max((n for n in networks if ip in n[0]), key=lambda n: n[0].prefixlen)
        hops.append(best[1])
    lines = [f"{n} via {gw}" for n, gw in networks]
    prompt = (
        f"Таблица маршрутизации ниже. Через какой шлюз уйдут пакеты на {', '.join(map(str, ips))}? "
        "Ответ — имена шлюзов через пробел."
    )
    return Instance(
        prompt,
        " ".join(hops),
        {"routes": routes, "ips": [str(i) for i in ips]},
        code="\n".join(lines),
    )


@kind(Kind.COMPUTE)
def handshake_latency(rng: random.Random, runner: CodeRunner) -> Instance:
    rtt = rng.randrange(10, 300, 5)
    tls = rng.choice(["1.2", "1.3"])
    reuse = rng.random() < 0.3
    tcp_rtts = 0 if reuse else 1
    tls_rtts = 0 if reuse else (2 if tls == "1.2" else 1)
    first_byte = (tcp_rtts + tls_rtts + 1) * rtt
    prompt = (
        f"RTT до сервера {rtt} мс, сервер отвечает мгновенно. Клиент делает HTTPS-запрос по "
        f"TLS {tls}"
        + (" через уже открытое соединение" if reuse else " с новым соединением, без 0-RTT")
        + ". Через сколько миллисекунд придёт первый байт ответа? Ответ — число."
    )
    return Instance(prompt, str(first_byte), {"rtt": rtt, "tls": tls, "reuse": reuse})


GREP_PATTERNS = ["ERROR", "-i error", "-v INFO", "-E 'WARN|ERROR'", "-c svc-a"]


@kind(Kind.TRACE)
def grep_count(rng: random.Random, runner: CodeRunner) -> Instance:
    levels = [rng.choice(["INFO", "WARN", "ERROR", "DEBUG", "error"]) for _ in range(12)]
    lines = [
        f"2026-10-0{rng.randint(1, 9)} {lvl} svc-{rng.choice('abc')}: msg {i}"
        for i, lvl in enumerate(levels)
    ]
    patterns = rng.sample(GREP_PATTERNS, 3)
    counts = []
    commands = []
    for pattern in patterns:
        if pattern == "ERROR":
            count = sum(1 for line in lines if "ERROR" in line)
        elif pattern == "-i error":
            count = sum(1 for line in lines if "error" in line.lower())
        elif pattern == "-v INFO":
            count = sum(1 for line in lines if "INFO" not in line)
        elif pattern == "-E 'WARN|ERROR'":
            count = sum(1 for line in lines if "WARN" in line or "ERROR" in line)
        else:
            count = sum(1 for line in lines if "svc-a" in line)
        counts.append(count)
        commands.append(
            f"grep {pattern} app.log"
            if pattern.startswith("-c")
            else f"grep {pattern} app.log | wc -l"
        )
    prompt = (
        f"Что выведут команды {'; '.join(commands)}? Ответ — три числа через пробел по порядку "
        "команд."
    )
    return Instance(
        prompt,
        " ".join(map(str, counts)),
        {"lines": lines, "patterns": patterns},
        code="\n".join(lines),
    )


_DAEMONS = [("sshd", 22), ("nginx", 80), ("postgres", 5432), ("redis-server", 6379)]
_DAEMONS += [("node", 3000), ("prometheus", 9090), ("grafana", 3001)]


@kind(Kind.COMPUTE)
def listening_ports(rng: random.Random, runner: CodeRunner) -> Instance:
    host = f"192.168.{rng.randint(0, 9)}.{rng.randint(10, 250)}"
    sockets = []
    for name, port in rng.sample(_DAEMONS, 5):
        address = rng.choice(["0.0.0.0", "127.0.0.1", "[::]", "*", host, "[::1]"])
        sockets.append((name, port, address))
    # Снаружи доступны сокеты на всех адресах и на адресе хоста; [::] при bindv6only = 0
    # принимает и IPv4.
    reachable = {
        port: name for name, port, address in sockets if address not in ("127.0.0.1", "[::1]")
    }
    ports = [port for _, port, _ in sockets] + [rng.choice([8080, 443, 25])]
    asked = rng.sample(ports, 4)
    lines = [
        f'LISTEN 0 128 {address}:{port}  users:(("{name}",pid={rng.randint(300, 9000)},fd=6))'
        for name, port, address in sockets
    ]
    prompt = (
        f"На сервере {host} вывод ss -tlnp ниже, net.ipv6.bindv6only = 0, межсетевого экрана нет. "
        f"Кто ответит на TCP-подключение с другой машины к {host} на порты "
        f"{', '.join(map(str, asked))}? Ответ — имя процесса или «отказ» для каждого порта через "
        "пробел."
    )
    return Instance(
        prompt,
        " ".join(reachable.get(port, "отказ") for port in asked),
        {"host": host, "sockets": sockets, "asked": asked},
        code="\n".join(lines),
    )


@kind(Kind.COMPUTE)
def load_average(rng: random.Random, runner: CodeRunner) -> Instance:
    servers = []
    for name in rng.sample(["app-1", "app-2", "db-1", "cache-1", "batch-1", "web-1"], 4):
        cores = rng.choice([2, 4, 8, 16])
        load15 = round(cores * rng.uniform(0.2, 1.6), 2)
        load1 = round(load15 * rng.choice([0.5, 0.8, 1.3, 1.7]), 2)
        load5 = round((load1 + load15) / 2, 2)
        servers.append((name, cores, load1, load5, load15))
    overloaded = [name for name, cores, load1, _, _ in servers if load1 > cores]
    rising = [name for name, _, load1, _, load15 in servers if load1 > load15]
    lines = [
        f"{name}: ядер {cores}, load average: {l1:.2f}, {l5:.2f}, {l15:.2f}"
        for name, cores, l1, l5, l15 in servers
    ]
    prompt = (
        "Какие серверы перегружены прямо сейчас (средняя загрузка за минуту больше числа ядер) и "
        "у каких нагрузка растёт (за минуту больше, чем за 15 минут)? Ответ — имена перегруженных "
        "через пробел, затем «|», затем имена с растущей нагрузкой; пустой список — «нет»."
    )
    answer = f"{' '.join(overloaded) or 'нет'} | {' '.join(rising) or 'нет'}"
    return Instance(prompt, answer, {"servers": servers}, code="\n".join(lines))
