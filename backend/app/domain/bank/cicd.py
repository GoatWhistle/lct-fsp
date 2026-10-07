"""CI/CD: стадии и needs в GitLab CI, правила запуска задач, кэш по ключу, матрица GitHub
Actions, семантическое версионирование, учёт минут, метрики DORA, Helm, нестабильные задачи."""

import math
import random
import statistics
from collections.abc import Callable, Mapping
from typing import Any

from app.domain.bank.family import Instance, rounded

_STAGES = {
    "build": ["compile", "docker", "assets"],
    "test": ["unit", "lint", "integration", "e2e"],
    "deploy": ["staging", "docs"],
}


def stage_duration(rng: random.Random) -> Instance:
    jobs = []
    for stage, names in _STAGES.items():
        for name in rng.sample(names, rng.randint(1, len(names))):
            jobs.append((stage, name, rng.randint(1, 12)))
    ends: dict[str, int] = {}
    start = 0
    for stage in _STAGES:
        longest = max(d for s, _, d in jobs if s == stage)
        ends[stage] = start + longest
        start = ends[stage]
    lines = ["stages: [build, test, deploy]", ""]
    lines += [f"{name}:  stage: {stage}  # идёт {d} мин" for stage, name, d in jobs]
    prompt = (
        "Пайплайн GitLab CI, раннеров хватает на все задачи сразу, все задачи успешны. Через "
        "сколько минут после старта начнётся стадия deploy и через сколько закончится весь "
        "пайплайн? Ответ — два числа через пробел."
    )
    return Instance(
        prompt,
        f"{ends['test']} {ends['deploy']}",
        {"jobs": jobs},
        code="\n".join(lines),
    )


def needs_dag(rng: random.Random) -> Instance:
    names = ["compile", "lint", "unit", "image", "e2e", "deploy"]
    stage_of = {"compile": 0, "lint": 0, "unit": 1, "image": 1, "e2e": 2, "deploy": 2}
    durations = {n: rng.randint(1, 15) for n in names}
    needs = {
        "compile": [],
        "lint": [],
        "unit": ["compile"],
        "image": rng.choice([["compile"], ["compile", "lint"]]),
        "e2e": rng.choice([["image"], ["image", "unit"]]),
        "deploy": rng.choice([["image"], ["unit", "image"], ["lint", "image"]]),
    }
    finish: dict[str, int] = {}
    for n in names:
        finish[n] = max((finish[d] for d in needs[n]), default=0) + durations[n]
    by_stage = [0, 0, 0]
    start = 0
    for stage in range(3):
        start += max(durations[n] for n in names if stage_of[n] == stage)
        by_stage[stage] = start
    lines = ["stages: [build, test, release]", ""]
    for n in names:
        stage_name = ["build", "test", "release"][stage_of[n]]
        need = f"  needs: [{', '.join(needs[n])}]" if needs[n] else "  needs: []"
        lines.append(f"{n}:  stage: {stage_name}{need}  # идёт {durations[n]} мин")
    prompt = (
        "Пайплайн GitLab CI, раннеров хватает на все задачи сразу, все задачи успешны. Задача с "
        "needs стартует, как только закончились перечисленные задачи, с needs: [] — сразу. Через "
        "сколько минут закончится пайплайн с needs и сколько бы он шёл, если убрать needs и "
        "оставить только стадии? Ответ — два числа через пробел."
    )
    return Instance(
        prompt,
        f"{max(finish.values())} {by_stage[-1]}",
        {"durations": durations, "needs": needs},
        code="\n".join(lines),
    )


_EVENTS: list[tuple[str, dict[str, Any]]] = [
    ("push в main, изменён src/app.py", {"source": "push", "branch": "main", "files": ["src"]}),
    ("push в main, изменён docs/guide.md", {"source": "push", "branch": "main", "files": ["docs"]}),
    (
        "push в существующую ветку feature/login, изменён src/app.py",
        {"source": "push", "branch": "feature/login", "files": ["src"]},
    ),
    ("merge request из feature/login", {"source": "merge_request_event", "files": ["src"]}),
    ("merge request с правкой docs/guide.md", {"source": "merge_request_event", "files": ["docs"]}),
    ("тег v1.4.0", {"source": "push", "tag": "v1.4.0"}),
    ("запуск по расписанию из main", {"source": "schedule", "branch": "main"}),
]

_CONDITIONS: list[tuple[str, Callable[[dict[str, Any]], bool]]] = [
    (
        'if: $CI_PIPELINE_SOURCE == "merge_request_event"',
        lambda e: e["source"] == "merge_request_event",
    ),
    ('if: $CI_COMMIT_BRANCH == "main"', lambda e: e.get("branch") == "main"),
    ("if: $CI_COMMIT_TAG", lambda e: "tag" in e),
    ('if: $CI_PIPELINE_SOURCE == "schedule"', lambda e: e["source"] == "schedule"),
    # В пайплайнах тегов и расписания GitLab считает changes выполненным.
    (
        "changes: [docs/**/*]",
        lambda e: "docs" in e.get("files", []) or "tag" in e or e["source"] == "schedule",
    ),
]


def rules_first_match(rng: random.Random) -> Instance:
    rules = []
    for i in rng.sample(range(len(_CONDITIONS)), rng.randint(2, 4)):
        when = rng.choice(["never", "on_success", "manual"])
        rules.append((i, when))
    fallback = rng.random() < 0.5
    events = rng.sample(_EVENTS, 5)
    answers = []
    for _, event in events:
        decision = "да" if fallback else "нет"
        for i, when in rules:
            if _CONDITIONS[i][1](event):
                decision = {"never": "нет", "on_success": "да", "manual": "вручную"}[when]
                break
        answers.append(decision)
    lines = ["deploy:", "  rules:"]
    for i, when in rules:
        lines.append(f"    - {_CONDITIONS[i][0]}")
        lines.append(f"      when: {when}")
    if fallback:
        lines.append("    - when: on_success")
    rows = "\n".join(f"{n}. {text}" for n, (text, _) in enumerate(events, 1))
    prompt = (
        "Правила задачи deploy проверяются по порядку, срабатывает первое подходящее; если не "
        "подошло ни одно, задачи в пайплайне нет. changes в push-пайплайне сравнивает с прошлым "
        "коммитом, в тегах и расписании changes считается выполненным. Будет ли задача в "
        "пайплайне? Ответ — «да», «нет» или «вручную» для каждого события через пробел."
    )
    return Instance(
        prompt,
        " ".join(answers),
        {"rules": rules, "fallback": fallback, "events": [text for text, _ in events]},
        code="\n".join(lines) + "\n\nСобытия:\n" + rows,
    )


def semver_bump(rng: random.Random) -> Instance:
    major, minor, patch = rng.randint(1, 9), rng.randint(0, 20), rng.randint(0, 20)
    pool = [
        ("fix: падение на пустой корзине", "patch"),
        ("docs: обновить README", None),
        ("feat: оплата по СБП", "minor"),
        ("refactor: вынести клиент API", None),
        ("perf: кэш каталога", "patch"),
        ("feat!: новый формат ответа /orders", "major"),
        ("chore: обновить зависимости", None),
        ("fix: таймаут запроса\n\nBREAKING CHANGE: убран параметр retries", "major"),
        ("test: сценарий возврата", None),
    ]
    weights = [3, 2, 2, 2, 1, 1, 2, 1, 2]
    commits: list[tuple[str, str | None]] = []
    count = rng.randint(2, 4)
    while len(commits) < count:
        commit = rng.choices(pool, weights)[0]
        if commit not in commits:
            commits.append(commit)
    bumps = {b for _, b in commits}
    if "major" in bumps:
        version = f"{major + 1}.0.0"
    elif "minor" in bumps:
        version = f"{major}.{minor + 1}.0"
    elif "patch" in bumps:
        version = f"{major}.{minor}.{patch + 1}"
    else:
        version = "нет"
    prompt = (
        f"Последний релиз — v{major}.{minor}.{patch}. Релизный инструмент читает коммиты по "
        "Conventional Commits и поднимает версию по SemVer; коммиты без fix, perf, feat и "
        "BREAKING CHANGE релиза не создают. Какой будет следующая версия? Ответ — версия без v "
        "или «нет», если релиза не будет."
    )
    return Instance(
        prompt,
        version,
        {"base": [major, minor, patch], "commits": [c for c, _ in commits]},
        code="\n---\n".join(c for c, _ in commits),
    )


_MULTIPLIERS = {"Linux": 1, "Windows": 2, "macOS": 10}


def pipeline_minutes(rng: random.Random) -> Instance:
    jobs = []
    for _ in range(rng.randint(3, 5)):
        system = rng.choice(list(_MULTIPLIERS))
        seconds = rng.randint(20, 900)
        jobs.append((system, seconds))
    billed = sum(math.ceil(s / 60) * _MULTIPLIERS[system] for system, s in jobs)
    raw = sum(math.ceil(s / 60) for _, s in jobs)
    lines = [f"{i}. {system}, {s // 60} мин {s % 60} с" for i, (system, s) in enumerate(jobs, 1)]
    prompt = (
        "Хостинг CI округляет время каждой задачи вверх до целой минуты и умножает на "
        "коэффициент раннера: Linux ×1, Windows ×2, macOS ×10. Сколько минут занял пайплайн по "
        "округлённому времени задач и сколько минут спишут? Ответ — два числа через пробел."
    )
    return Instance(prompt, f"{raw} {billed}", {"jobs": jobs}, code="\n".join(lines))


def cache_key_hits(rng: random.Random) -> Instance:
    versions = ["v1"]
    pipelines = []
    current = "v1"
    for i in range(1, 8):
        roll = rng.random()
        if roll < 0.3:
            current = f"v{len(versions) + 1}"
            versions.append(current)
            pipelines.append((i, f"изменили package-lock.json, стало состояние {current}", current))
        elif roll < 0.4 and len(versions) > 1:
            current = versions[-2]
            pipelines.append((i, f"откатили package-lock.json к состоянию {current}", current))
        else:
            what = rng.choice(["изменили src/app.ts", "изменили README.md", "без изменений"])
            pipelines.append((i, what, current))
    seen: set[str] = set()
    letters = []
    for _, _, lock in pipelines:
        letters.append("П" if lock in seen else "М")
        seen.add(lock)
    lines = [f"{i}. {what}" for i, what, _ in pipelines]
    prompt = (
        "У задачи кэш с key: files: [package-lock.json] — ключ зависит только от содержимого "
        "этого файла. Кэш пишется после успешной задачи и не истекает; все задачи успешны. "
        "Пайплайны идут по порядку, первый — на пустом кэше, package-lock.json в нём — в "
        "состоянии v1. Попадёт ли каждый пайплайн в кэш? "
        "Ответ — по букве на пайплайн подряд: П — попадание, М — промах."
    )
    return Instance(
        prompt,
        "".join(letters),
        {"pipelines": [[i, what] for i, what, _ in pipelines]},
        code="\n".join(lines),
    )


def matrix_jobs(rng: random.Random) -> Instance:
    oses = rng.sample(["ubuntu-latest", "windows-latest", "macos-latest"], rng.randint(2, 3))
    pythons = rng.sample(["3.10", "3.11", "3.12", "3.13"], rng.randint(2, 4))
    combos: list[dict[str, object]] = [{"os": o, "python": p} for o in oses for p in pythons]
    excludes: list[dict[str, object]] = []
    for _ in range(rng.randint(0, 2)):
        if rng.random() < 0.5:
            excludes.append({"os": rng.choice(oses), "python": rng.choice(pythons)})
        else:
            excludes.append({"os": rng.choice(oses)})
    combos = [c for c in combos if not any(all(c[k] == v for k, v in e.items()) for e in excludes)]
    includes: list[dict[str, object]] = []
    for _ in range(rng.randint(1, 3)):
        kind = rng.random()
        if kind < 0.4:
            includes.append(
                {"os": rng.choice(oses), "python": rng.choice(pythons), "coverage": True}
            )
        elif kind < 0.7:
            includes.append({"os": "ubuntu-latest", "python": "3.14-dev"})
        else:
            includes.append({"os": rng.choice(oses), "experimental": True})
    jobs = [dict(c) for c in combos]
    for inc in includes:
        # include дополняет исходные сочетания, где не перезапишет значения os и python; если
        # таких нет — добавляет новое сочетание. С добавленными include не сопоставляется.
        targets = [
            job
            for job, original in zip(jobs, combos, strict=False)
            if all(original[k] == v for k, v in inc.items() if k in ("os", "python"))
        ]
        if targets:
            for job in targets:
                job.update(inc)
        else:
            jobs.append(dict(inc))
    ubuntu = sum(1 for j in jobs if j.get("os") == "ubuntu-latest")

    def value(key: str, v: object) -> str:
        # Версии Python — в кавычках: без них YAML прочтёт 3.10 как число 3.1.
        if isinstance(v, bool):
            return str(v).lower()
        return f'"{v}"' if key == "python" else str(v)

    def render(entry: Mapping[str, object]) -> str:
        return "{" + ", ".join(f"{k}: {value(k, v)}" for k, v in entry.items()) + "}"

    lines = [
        "strategy:",
        "  matrix:",
        f"    os: [{', '.join(oses)}]",
        f"    python: [{', '.join(f'"{p}"' for p in pythons)}]",
    ]
    if excludes:
        lines.append("    exclude:")
        lines += [f"      - {render(e)}" for e in excludes]
    lines.append("    include:")
    lines += [f"      - {render(i)}" for i in includes]
    prompt = (
        "Сколько задач запустит эта матрица GitHub Actions и сколько из них на ubuntu-latest? "
        "Ответ — два числа через пробел."
    )
    return Instance(
        prompt,
        f"{len(jobs)} {ubuntu}",
        {"oses": oses, "pythons": pythons, "excludes": excludes, "includes": includes},
        code="\n".join(lines),
    )


def dora_metrics(rng: random.Random) -> Instance:
    weeks = 2
    deploys = []
    for day in sorted(rng.sample(range(1, 15), rng.randint(5, 9))):
        lead = rng.choice([2, 4, 6, 8, 12, 20, 30, 48])
        failed = rng.random() < 0.25
        restore = rng.choice([30, 45, 60, 90, 120, 240]) if failed else None
        deploys.append((day, lead, failed, restore))
    per_week = len(deploys) / weeks
    failures = [d for d in deploys if d[2]]
    cfr = 100 * len(failures) / len(deploys)
    median_lead = statistics.median(d[1] for d in deploys)
    mttr = statistics.mean(d[3] for d in failures if d[3] is not None) if failures else 0
    lines = [
        f"день {day}: от коммита до прода {lead} ч"
        + (f", вызвал сбой, восстановили за {restore} мин" if failed else "")
        for day, lead, failed, restore in deploys
    ]
    prompt = (
        "Выкатки в прод за две недели ниже. Найдите частоту выкаток в неделю, долю выкаток со "
        "сбоем (%), медианное время от коммита до прода (ч) и среднее время восстановления "
        "(мин; если сбоев не было — 0). Ответ — четыре числа через пробел, каждое округлите до "
        "десятых."
    )
    answer = " ".join(rounded(v, 1) for v in (per_week, cfr, median_lead, mttr))
    return Instance(prompt, answer, {"deploys": deploys}, code="\n".join(lines))


def helm_rollback(rng: random.Random) -> Instance:
    revision = 1
    app = "1.0.0"
    history = {1: app}
    failed: set[int] = set()
    lines = ["helm install shop ./chart --set image.tag=1.0.0"]
    minor = 0
    for _ in range(rng.randint(4, 6)):
        action = rng.choice(["upgrade", "upgrade", "atomic-fail", "rollback"])
        if action == "rollback" and revision > 1:
            target = rng.choice([r for r in range(1, revision) if r not in failed])
            revision += 1
            app = history[target]
            lines.append(f"helm rollback shop {target}")
        elif action == "atomic-fail":
            minor += 1
            # Неудачный upgrade с --atomic: ревизия failed, затем автоматический откат — ещё одна.
            revision += 2
            lines.append(
                f"helm upgrade shop ./chart --atomic --set image.tag=1.{minor}.0"
                "  # поды не стали Ready"
            )
            failed.add(revision - 1)
            history[revision - 1] = f"1.{minor}.0"
        else:
            minor += 1
            revision += 1
            app = f"1.{minor}.0"
            lines.append(f"helm upgrade shop ./chart --set image.tag={app}")
        history[revision] = app
    prompt = (
        "Команды ниже выполнены по порядку, все успешны, кроме отмеченной. Какой номер у текущей "
        "ревизии релиза shop и какой тег образа сейчас работает? Ответ — два значения через "
        "пробел."
    )
    return Instance(prompt, f"{revision} {app}", {"lines": lines}, code="\n".join(lines))


def flaky_pipeline(rng: random.Random) -> Instance:
    jobs = rng.randint(4, 20)
    p = rng.choice([0.02, 0.05, 0.1, 0.15, 0.2])
    retries = rng.randint(0, 2)
    job_ok = 1 - p ** (retries + 1)
    pipeline_ok = job_ok**jobs
    runs = jobs * sum(p**k for k in range(retries + 1))
    prompt = (
        f"В пайплайне {jobs} независимых задач, каждая падает с вероятностью "
        f"{rounded(p * 100, 0)} % при каждом запуске, у каждой retry: {retries} — упавшая "
        f"задача перезапускается до {retries} раз. Какова вероятность, что пайплайн пройдёт, "
        "и сколько запусков задач в среднем он сделает? Ответ — два числа через пробел: "
        "вероятность до тысячных, запуски до десятых."
    )
    return Instance(
        prompt,
        f"{rounded(pipeline_ok, 3)} {rounded(runs, 1)}",
        {"jobs": jobs, "p": p, "retries": retries},
    )
