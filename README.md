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

Кандидат без категории попадает на путь к ней: опрос (направление — специализация) → выбор
грейда → тест → результат — уровень с погрешностью, вероятность каждого грейда, категория и
профиль навыков по темам. Тест адаптивный и готов для всех специализаций: следующее задание выбирается
по текущей оценке уровня, тест останавливается, когда уровень определён с нужной точностью, —
у каждого кандидата свой набор заданий и свои экземпляры.

Кандидат в любой момент, кроме самого теста, заполняет профиль: ФИО, контакты, роли, стаж,
стек из справочника с автодополнением, софт-скиллы и ожидания: формат, город, зарплата и, по
желанию, интересные сферы бизнеса. Все суммы на платформе — в месяц до вычета НДФЛ, так и
подписаны. «Скачать PDF» собирает профиль единого вида: категория и профиль навыков, если тест
пройден, и самоописание. Работодатель видит кандидата обезличенной карточкой — без ФИО, контактов,
свободного текста («о себе», роли, софт-скиллы) и ожидаемой зарплаты.

Работодатель заполняет профиль компании (название, сфера деятельности, описание, контакты) и
заводит потребности: кого ищет, чем занимается команда, специализация, грейд, стек, формат, город и
вилка. Важность тем выводится из стека прямо в форме, её можно поправить.

В карточке потребности — «Сформировать подборку»: кандидаты с категорией потребности, затем
«близкие» соседнего грейда, по убыванию соответствия. У каждого — соответствие и его объяснение:
вклад каждой темы и самоописанного стека, сумма вкладов равна соответствию. Карточка кандидата
обезличена. Подборка сохраняется и открывается позже с той же выдачей; «Перестроить» создаёт
новую по текущим данным.

Порты и секрет подписи входа меняются в `.env` — образец в [`.env.example`](.env.example).

## Тесты

```sh
docker compose run --rm --build tests
```

Тесты ходят в бэкенд через HTTP API; на сервере PostgreSQL создаётся временная база и
удаляется после прогона. Без Docker Compose, с [uv](https://docs.astral.sh/uv/) и Docker:
`cd backend && uv run pytest` — PostgreSQL поднимется в контейнере сам.

Стенд валидации — синтетические кандидаты с известной истиной проходят те же сценарии теста и
калибровки, что HTTP, на in-memory хранилищах. Команды из `backend/`:

- `uv run python -m validation` — сходимость калибровки и сравнение адаптивного теста с
  фиксированным бланком по всем специализациям;
- `uv run python -m validation honesty` — честность погрешности уровня и стабильность грейда на
  прогретом банке D1 (`--seed`, `--candidates`, `--pairs`);
- `uv run python -m validation tune` — подбор поправки погрешности `level_sd_inflation` на
  настроечном наборе D3.

Банк заданий — тоже из `backend/`:

- `uv run python -m bank_report` — отчёт покрытия в markdown: доля трассировки по темам,
  сценарные семейства у middle и senior, ячейки «тема × грейд» без семейств и без описания в
  матрице грейдов; с `--calibration` — и сверка сложности с экспертной по калибровке из базы;
- `uv run python -m bank_report matrix` — пересобрать [`docs/grade-matrix.md`](docs/grade-matrix.md)
  из `config/grade_matrix.yaml`.

## Устройство

```
backend/                 FastAPI + SQLAlchemy + Alembic, PostgreSQL
  main.py                сборка прода вручную: `create_app` (запуск — `uvicorn --factory
                         main:create_app`) и синхронизация справочника `sync_catalog`
  composition.py         общая проводка сценариев из портов — для прода и стенда
  settings.py            настройки окружения `Settings` и параметры механик `Mechanics`
  validation/            стенд валидации: сборка `main.py`, синтетика, команды
  app/                   только слои — docs/adr/0001-layers-and-ports.md
    domain/              сущности и правила без библиотек: тест, категория, профиль навыков,
                         подборка, учётки, справочники; банк семейств — domain/bank/
    usecase/             сценарии на единице работы и порты (`interface.py`)
    controller/          роутеры FastAPI, схемы Pydantic, зависимости, guard ролей
    adapter/             реализации портов: модель навыка IRT, выбор задания, калибровка,
                         почта, PDF, пароли, токен входа, файл справочника
    repository/          хранилища на Postgres, ORM всех таблиц (`orm/`), in-memory (`memory/`)
  config/mechanics.yaml  параметры механик — те же, что в docs/parameters.md
  config/catalog.yaml    справочники: грейды, сферы бизнеса, специализации, темы, технологии
  migrations/            миграции схемы
  tests/                 тесты через HTTP API и сценарии на in-memory хранилищах
frontend/                React + TypeScript (Vite), на стенде — nginx
docker-compose.yml       PostgreSQL, бэкенд, фронт, Mailpit
```

Зависимости слоёв идут внутрь, к `domain`; `tests/test_layers.py` это проверяет. Сущность
проходит все слои под одним именем: учётки — `domain/account.py`, `usecase/account.py`,
`controller/auth.py`, `repository/account.py`; потребность — `need.py` в каждом слое; путь
кандидата к категории — `domain/attempt.py`, `usecase/attempt.py`, `controller/path.py`,
`repository/attempt.py`; подборка — `selection.py`, P(принятия) — за портом `AcceptanceModel`;
приглашение — `invitation.py` в каждом слое, статус «истекло» выводит домен при чтении.
Вход — по email и паролю, пароль хранится хэшем argon2, сессия — подписанный токен в
httpOnly-cookie. Права проверяет бэкенд: разделы `/api/candidate/*` и `/api/employer/*`
отвечают 403 чужой роли.

## Разработка

Бэкенд локально — база и почта из compose, код с перезагрузкой:

```sh
docker compose up -d db mailpit
cd backend
uv sync
uv run alembic upgrade head
uv run python -c 'import main; main.sync_catalog()'
uv run uvicorn --factory main:create_app --reload
```

Фронт локально — `cd frontend && npm install && npm run dev`, http://localhost:3000, запросы
`/api` проксируются на `:8000`.

Проверки перед PR:

```sh
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
cd frontend && npm run lint && npm run build
```

### Образцы

- **Новая сущность** — по слоям, файлы под одним именем
  ([`docs/adr/0001-layers-and-ports.md`](docs/adr/0001-layers-and-ports.md)):
  1. `app/domain/<имя>.py` — dataclass-ы и правила без SQLAlchemy, Pydantic и FastAPI;
  2. `app/usecase/<имя>.py` — сценарий-класс на единице работы, каждый вызов — блок
     `with uow:`; хранилище — порт-`Protocol` в `app/usecase/interface.py`;
  3. `app/repository/<имя>.py` — реализация порта, ORM таблицы — `app/repository/orm/<имя>.py`
     и импорт в `app/repository/orm/__init__.py` (по нему миграции видят таблицы); наружу —
     доменные значения, не строки ORM;
  4. `app/controller/<имя>.py` и `<имя>_schemas.py` — роутер и схемы; сценарий приходит
     зависимостью из `app/controller/deps.py`;
  5. проводка — фабрика сценария в `backend/composition.py`, реализации — в `create_app`
     (`backend/main.py`), там же подключается роутер.
- **Миграция** — `uv run alembic revision --autogenerate -m "short english slug"`, затем
  прочитать и поправить. Тест `test_models_match_migrations` падает, если модели разошлись с
  миграциями. Если после слияния веток у миграций две головы — `uv run alembic merge heads`.
- **Подключение к базе** — движок только через `create_db_engine`
  (`app/repository/database.py`): время из базы приходит в UTC при любом часовом поясе
  сервера. Временная база тестов — в `Europe/Moscow`, поэтому время, зависящее от пояса базы,
  роняет тесты.
- **Справочники** — данные в `backend/config/catalog.yaml`, не в коде. Бэкенд при старте
  синхронизирует их с базой (`sync_catalog` в `backend/main.py`, та же команда — из
  «Разработки»); коды стабильны — на них ссылаются тест, профиль и подбор.
- **Параметры механик** — числа из [`docs/parameters.md`](docs/parameters.md) под теми же
  именами в `config/mechanics.yaml` и полях `Mechanics` (`backend/settings.py`); в эндпоинт
  приходят через `MechanicsDep`. Константами в коде не пишутся. Новый параметр или значение — в
  доке и конфиге одним PR: `test_mechanics_config.py` сверяет их.
- **Ошибки** — подкласс `DomainError` в `app/domain/errors.py` с `code` и `message`
  по-русски, без HTTP-статуса. Статус — строка в `STATUS` (`app/controller/errors.py`);
  эндпоинт перечисляет ошибки в `responses=error_responses(...)`, и коды попадают в OpenAPI.
- **Разделы роли** — роутер с префиксом `/api/candidate` или `/api/employer`,
  `dependencies=role_guard(Role.…)` и `responses=ROLE_RESPONSES` (см.
  `app/controller/cabinets.py`).
- **Порт внешней системы** — по образцу почты, правило —
  [`docs/adr/0001-layers-and-ports.md`](docs/adr/0001-layers-and-ports.md):
  1. порт — `Protocol` в `app/usecase/interface.py` (`Mailer`); на входе и выходе только типы из
     `app/domain` (`Mail` в `app/domain/mail.py`), без ORM, Pydantic и типов библиотеки;
  2. реализация — в `app/adapter/` (`SmtpMailer` в `app/adapter/mail.py`); библиотеку и протокол
     системы импортирует только она — `test_layers.py` это проверяет для SMTP и fpdf2;
  3. сборка — в `create_app` (`backend/main.py`): адаптер создаётся там и передаётся в
     проводку `composition.py`, она отдаёт его сценарию (`Accounts` шлёт письмо подтверждения);
  4. тестовая реализация — тоже в `app/adapter/` (`MemoryMailer`); тесты подставляют её через
     параметр `create_app`, хелперы поверх — в `tests/conftest.py` (`Outbox`).
- **Тест** — через HTTP API, фикстуры из `tests/conftest.py`: `client` — аноним,
  `signed_in(Role.candidate)` — вошедший пользователь роли, `outbox` — отправленные письма.
- **Типы API на фронте** генерируются из OpenAPI: при запущенном бэкенде `npm run api:types`.
