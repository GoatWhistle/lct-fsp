"""Заглушка ФСП: realm Keycloak, который изображает ФСП ID, и файл реестра достижений.

Оба файла генерируются вместе из одного seed: у участников заданные `id`, поэтому `sub` в
токенах ФСП ID совпадает с ключами реестра. Данные синтетические. Оба файла коммитятся;
после правки персон — перегенерировать из `backend/`: `uv run python fsp_stub.py`.

Набор покрывает механику (mechanics.md, §11): победитель, призёр, только финалы, только отборы,
без истории, командные результаты с ролью, дисциплины без тем и участники с сильными
результатами для демонстрации расхождения ФСП и теста. Демо-участников
`demo-<специализация>-<грейд>` привязывает к своим кандидатам демо-засев `seed_demo.py`;
синтетический рынок стенда валидации пишет достижения в том же формате (`achievement`).
"""

import json
import random
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from settings import BACKEND_DIR, FSP_REGISTRY_FILE

SEED = 2026
REALM_FILE = BACKEND_DIR.parent / "keycloak" / "realm-fsp-id.json"
REALM = "fsp-id"
CLIENT_ID = "lct-platform"
# Секрет клиента стенда — тот же, что значение по умолчанию `FSP_ID_CLIENT_SECRET`.
CLIENT_SECRET = "dev-only-fsp-id-client-secret"
# Порты 3000/8000 — основной стенд, 3100/8100 — изолированный демо-стенд (`scripts/demo.sh`).
REDIRECT_URIS = (
    "http://localhost:3000/api/auth/fsp/callback",
    "http://localhost:8000/api/auth/fsp/callback",
    "http://localhost:3100/api/auth/fsp/callback",
    "http://localhost:8100/api/auth/fsp/callback",
)
# Пароль всех тестовых участников ФСП ID.
PASSWORD = "fsp-demo-2026"
YEARS = (2023, 2024, 2025, 2026)

EVENTS = {
    "algorithmic": (
        "Чемпионат России по алгоритмическому программированию",
        "Кубок ФСП по алгоритмическому программированию",
        "Всероссийские соревнования «Осенний алгоритм»",
    ),
    "product": (
        "Чемпионат России по продуктовому программированию",
        "Всероссийский хакатон ФСП «Цифровой регион»",
        "Кубок ФСП по продуктовому программированию",
    ),
    "security": (
        "Чемпионат России по программированию систем информационной безопасности",
        "Всероссийские соревнования ФСП по защите информации",
    ),
    "robotics": ("Кубок ФСП по программированию робототехники",),
    "uav": ("Чемпионат ФСП по программированию беспилотных авиационных систем",),
}

# Дисциплины, в которых выступают специалисты специализации, — синтетический рынок стенда и
# демо-участники.
DISCIPLINES = {
    "backend": ("algorithmic", "product", "security"),
    "frontend": ("algorithmic", "product"),
    "data-ml": ("algorithmic", "product"),
    "qa": ("product", "security"),
    "devops": ("product", "security"),
}

# Тип результата → места в итоговой таблице.
PLACES = {"winner": (1, 1), "prize": (2, 3), "finalist": (4, 30)}

Plan = tuple[tuple[str, str, str | None], ...]


@dataclass(frozen=True)
class Persona:
    """Тестовый участник: логин ФСП ID и план результатов — тип, дисциплина, роль в команде."""

    username: str
    first_name: str
    last_name: str
    plan: Plan
    email_verified: bool = True


PERSONAS = (
    Persona(
        "fsp-winner",
        "Алина",
        "Победова",
        (
            ("winner", "algorithmic", None),
            ("prize", "algorithmic", None),
            ("finalist", "product", None),
        ),
    ),
    Persona(
        "fsp-prize",
        "Борис",
        "Призёров",
        (("prize", "product", "backend"), ("finalist", "algorithmic", None)),
    ),
    Persona(
        "fsp-finalist",
        "Вера",
        "Финалова",
        (
            ("finalist", "algorithmic", None),
            ("finalist", "product", None),
            ("finalist", "security", None),
        ),
    ),
    Persona(
        "fsp-qualifier",
        "Глеб",
        "Отборов",
        (
            ("participant", "algorithmic", None),
            ("participant", "product", None),
            ("participant", "security", None),
        ),
    ),
    Persona("fsp-no-history", "Дарья", "Новикова", ()),
    Persona(
        "fsp-team-frontend",
        "Егор",
        "Командин",
        (("winner", "product", "frontend"), ("finalist", "product", "frontend")),
    ),
    Persona("fsp-team-data", "Жанна", "Данилова", (("prize", "product", "data-ml"),)),
    Persona("fsp-team-qa", "Захар", "Тестов", (("finalist", "product", "qa"),)),
    Persona("fsp-team-devops", "Ирина", "Деплоева", (("winner", "product", "devops"),)),
    Persona(
        "fsp-security",
        "Кирилл",
        "Защитин",
        (("winner", "security", None), ("prize", "security", None)),
    ),
    Persona(
        "fsp-robotics",
        "Лидия",
        "Роботова",
        (("prize", "robotics", None), ("finalist", "uav", None)),
    ),
    # Сильные результаты — пройдите тест слабо, чтобы увидеть расхождение ФСП и теста.
    Persona(
        "fsp-divergent-algo",
        "Максим",
        "Разногласов",
        (("winner", "algorithmic", None), ("winner", "algorithmic", None)),
    ),
    Persona(
        "fsp-divergent-product",
        "Нина",
        "Расходова",
        (("winner", "product", "backend"), ("winner", "security", None)),
    ),
    # Email в ФСП ID не подтверждён — вход через ФСП ID откажет с понятным текстом.
    Persona(
        "fsp-unverified",
        "Олег",
        "Неподтверждённый",
        (("finalist", "product", None),),
        email_verified=False,
    ),
)


# Демо-участники: по одному на категорию «специализация × грейд». Демо-засев (`seed_demo.py`)
# привязывает их к демо-кандидатам с ФСП: вход в ФСП ID под `demo-<специализация>-<грейд>`
# открывает кандидата этой категории. Результат растёт с грейдом.
DEMO_NAMES = (
    ("Антон", "Бэкендов"),
    ("Белла", "Серверова"),
    ("Валерий", "Запросов"),
    ("Галина", "Очередёва"),
    ("Денис", "Вёрсткин"),
    ("Ева", "Компонентова"),
    ("Жора", "Браузеров"),
    ("Зоя", "Реактова"),
    ("Игорь", "Выборкин"),
    ("Карина", "Признакова"),
    ("Лев", "Моделев"),
    ("Мария", "Датасетова"),
    ("Никита", "Проверкин"),
    ("Ольга", "Багова"),
    ("Павел", "Автотестов"),
    ("Римма", "Нагрузова"),
    ("Семён", "Конвейеров"),
    ("Таисия", "Кластерова"),
    ("Ульян", "Скриптов"),
    ("Фаина", "Метрикова"),
)
DEMO_GRADES = ("intern", "junior", "middle", "senior")


def demo_username(specialization: str, grade: str) -> str:
    return f"demo-{specialization}-{grade}"


def _demo_plan(specialization: str, grade: str) -> Plan:
    first, *_ = DISCIPLINES[specialization]
    match grade:
        case "intern":
            return (("participant", first, None), ("finalist", "product", None))
        case "junior":
            return (("finalist", first, None),)
        case "middle":
            return (("prize", "product", specialization), ("finalist", first, None))
        case _:
            return (("winner", first, None), ("prize", "product", specialization))


DEMO_PERSONAS = tuple(
    Persona(demo_username(code, grade), first, last, _demo_plan(code, grade))
    for (code, grade), (first, last) in zip(
        ((c, g) for c in DISCIPLINES for g in DEMO_GRADES), DEMO_NAMES, strict=True
    )
)


def achievement(
    rng: random.Random, result: str, discipline: str, role: str | None
) -> dict[str, Any]:
    day = date(rng.choice(YEARS), rng.randint(1, 9), rng.randint(1, 28))
    low, high = PLACES.get(result, (0, 0))
    return {
        "event": rng.choice(EVENTS[discipline]),
        "date": day.isoformat(),
        "discipline": discipline,
        "place": rng.randint(low, high) if result in PLACES else None,
        "fsp_result": result,
        "team_role": role,
    }


def generate(seed: int = SEED) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    """Realm export и реестр: тот же seed — те же файлы байт в байт."""
    rng = random.Random(seed)
    users = []
    registry: dict[str, list[dict[str, Any]]] = {}
    for persona in (*PERSONAS, *DEMO_PERSONAS):
        sub = str(uuid.UUID(int=rng.getrandbits(128), version=4))
        achievements = [achievement(rng, *step) for step in persona.plan]
        registry[sub] = sorted(achievements, key=lambda a: a["date"])
        users.append(
            {
                "id": sub,
                "username": persona.username,
                "email": f"{persona.username}@fsp-id.example",
                "emailVerified": persona.email_verified,
                "firstName": persona.first_name,
                "lastName": persona.last_name,
                "enabled": True,
                "credentials": [{"type": "password", "value": PASSWORD, "temporary": False}],
            }
        )
    realm = {
        "realm": REALM,
        "displayName": "ФСП ID",
        "enabled": True,
        "sslRequired": "none",
        "registrationAllowed": False,
        "loginWithEmailAllowed": True,
        "internationalizationEnabled": True,
        "supportedLocales": ["ru"],
        "defaultLocale": "ru",
        "clients": [
            {
                "clientId": CLIENT_ID,
                "name": "Подбор ИТ-специалистов ФСП",
                "enabled": True,
                "protocol": "openid-connect",
                "publicClient": False,
                "clientAuthenticatorType": "client-secret",
                "secret": CLIENT_SECRET,
                "standardFlowEnabled": True,
                "directAccessGrantsEnabled": False,
                "implicitFlowEnabled": False,
                "serviceAccountsEnabled": False,
                "redirectUris": list(REDIRECT_URIS),
                "webOrigins": [],
                "attributes": {"pkce.code.challenge.method": "S256"},
            }
        ],
        "users": users,
    }
    return realm, registry


def dump(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def main() -> None:
    realm, registry = generate()
    REALM_FILE.parent.mkdir(exist_ok=True)
    REALM_FILE.write_text(dump(realm), encoding="utf-8")
    Path(FSP_REGISTRY_FILE).write_text(dump(registry), encoding="utf-8")
    print(f"Записаны {REALM_FILE} и {FSP_REGISTRY_FILE}")


if __name__ == "__main__":
    main()
