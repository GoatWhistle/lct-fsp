# Подбор ИТ-специалистов ФСП

Платформа подбора с обратной механикой: кандидат проходит опрос и адаптивный тест и получает
профиль навыков и категорию, работодатель описывает потребность, получает подборку с объяснением
и сам приглашает кандидата. Достижения ФСП — самый весомый сигнал профиля.

## Запуск

Нужен Docker с Compose v2. Из корня репо:

```sh
docker compose up --build
```

Когда стенд поднимется:

| Что | Адрес |
|---|---|
| Фронт | http://localhost:3000 |
| Swagger (OpenAPI) | http://localhost:8000/api/docs |
| Mailpit — письма подтверждения | http://localhost:8025 |

Путь для проверки: «Регистрация» → выбрать роль → письмо приходит в Mailpit → ссылка из письма
→ «Войти» → кабинет своей роли. Без подтверждения адреса вход закрыт.

Порты и секрет подписи входа меняются в `.env` — образец в [`.env.example`](.env.example).

## Тесты

```sh
docker compose run --rm tests
```

Тесты ходят в бэкенд через HTTP API; на сервере PostgreSQL создаётся временная база и
удаляется после прогона. Без Docker Compose, с [uv](https://docs.astral.sh/uv/) и Docker:
`cd backend && uv run pytest` — PostgreSQL поднимется в контейнере сам.

## Устройство

```
backend/                 FastAPI + SQLAlchemy + Alembic, PostgreSQL
  app/<модуль>/          models, schemas, service, router одного модуля
  app/assessment/catalog.yaml   справочники: грейды, специализации, темы, технологии
  config/mechanics.yaml  параметры механик
  migrations/            миграции схемы
  tests/                 тесты через HTTP API
frontend/                React + TypeScript (Vite), на стенде — nginx
docker-compose.yml       PostgreSQL, бэкенд, фронт, Mailpit
```

Модули бэкенда: `identity` — учётки, роли, подтверждение email; `assessment` — справочники
(дальше — тест и калибровка). Вход — по email и паролю, пароль хранится хэшем argon2, сессия —
подписанный токен в httpOnly-cookie. Права проверяет бэкенд: разделы `/api/candidate/*` и
`/api/employer/*` отвечают 403 чужой роли.

## Разработка

Бэкенд локально — база и почта из compose, код с перезагрузкой:

```sh
docker compose up -d db mailpit
cd backend
uv sync
uv run alembic upgrade head
uv run python -m app.assessment.catalog
uv run uvicorn app.main:app --reload
```

Фронт локально — `cd frontend && npm install && npm run dev`, http://localhost:3000, запросы
`/api` проксируются на `:8000`.

Проверки перед PR:

```sh
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app tests && uv run pytest
cd frontend && npm run lint && npm run build
```

### Образцы

- **Модуль** — пакет `backend/app/<модуль>/`: `models.py`, `schemas.py`, `service.py`,
  `router.py`. Роутер подключается в `app/main.py`, модели — импортом в `app/models.py`.
- **Миграция** — `uv run alembic revision --autogenerate -m "short english slug"`, затем
  прочитать и поправить. Тест `test_models_match_migrations` падает, если модели разошлись с
  миграциями. Если после слияния веток у миграций две головы — `uv run alembic merge heads`.
- **Справочники** — данные в `app/assessment/catalog.yaml`, не в коде. Бэкенд при старте
  синхронизирует их с базой; коды стабильны — на них ссылаются тест, профиль и подбор.
- **Параметры механик** — раздел в `config/mechanics.yaml` и модель в `app/config.py`
  (`Mechanics`); в эндпоинт приходят через `MechanicsDep`. Пороги и сроки не пишутся
  константами в коде: прогон стенда валидации фиксирует этот файл.
- **Ошибки** — подкласс `AppError` со `status_code`, `code` и `message` по-русски; эндпоинт
  перечисляет их в `responses=error_responses(...)`, и коды попадают в OpenAPI.
- **Разделы роли** — роутер с префиксом `/api/candidate` или `/api/employer`,
  `dependencies=role_guard(Role.…)` и `responses=ROLE_RESPONSES` (см. `app/cabinets.py`).
- **Тест** — через HTTP API, фикстуры из `tests/conftest.py`: `client` — аноним,
  `signed_in(Role.candidate)` — вошедший пользователь роли, `outbox` — отправленные письма.
- **Типы API на фронте** генерируются из OpenAPI: при запущенном бэкенде `npm run api:types`.
