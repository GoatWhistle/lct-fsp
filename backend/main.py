"""Сборка приложения — вручную, без DI-контейнера (docs/adr/0001-layers-and-ports.md).

На уровне модуля только определения функций: объект приложения строит
`uvicorn --factory main:create_app`, поэтому импорт `main` не читает конфиг и не открывает базу.
Новый роутер подключается в `create_app`.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.orm import sessionmaker

from app.adapter.acceptance import NoAcceptanceModel
from app.adapter.clock import SystemClock
from app.adapter.mail import SmtpMailer
from app.adapter.profile_pdf import FpdfProfileRenderer
from app.adapter.seed import SecureSeeds
from app.assessment.path_router import router as path_router
from app.assessment.router import router as catalog_router
from app.cabinets import candidate_router, employer_router
from app.company.router import router as company_router
from app.config import Mechanics, Settings
from app.controller.errors import install_error_handlers
from app.db import create_db_engine
from app.identity.router import router as auth_router
from app.matching.router import router as needs_router
from app.matching.router import selections_router
from app.profile.router import employer_router as candidates_router
from app.profile.router import router as profile_router
from app.repository.selection import SqlCandidatePool, SqlNeeds, SqlSelections
from app.repository.unit_of_work import SqlUnitOfWork
from app.usecase.interface import AcceptanceModel, Clock, Mailer, ProfilePdfRenderer, SeedSource
from app.usecase.selection import Selections


def description() -> str:
    """Описание API в OpenAPI."""
    return """
Платформа подбора ИТ-специалистов с обратной механикой.

Ошибки приходят телом `{"code", "message"}`: `code` — для кода фронта, `message` — для
пользователя. Вход — cookie `access_token` (httpOnly), её ставит `POST /api/auth/login`.
Разделы `/api/candidate` и `/api/employer` доступны только своей роли. Время — в UTC,
ISO 8601 с `Z`.
"""


def create_app(
    settings: Settings | None = None,
    mechanics: Mechanics | None = None,
    mailer: Mailer | None = None,
    profile_pdf_renderer: ProfilePdfRenderer | None = None,
    clock: Clock | None = None,
    seeds: SeedSource | None = None,
    acceptance: AcceptanceModel | None = None,
) -> FastAPI:
    settings = settings or Settings()
    mechanics = mechanics or Mechanics.from_yaml(settings.mechanics_file)
    engine = create_db_engine(settings.database_url, pool_pre_ping=True)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        engine.dispose()

    app = FastAPI(
        title="Подбор ИТ-специалистов ФСП",
        description=description(),
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.engine = engine
    app.state.settings = settings
    app.state.mechanics = mechanics
    session_factory = sessionmaker(engine, expire_on_commit=False)

    def unit_of_work() -> SqlUnitOfWork:
        return SqlUnitOfWork(session_factory())

    app.state.unit_of_work = unit_of_work
    app.state.mailer = mailer or SmtpMailer(
        settings.smtp_host, settings.smtp_port, settings.mail_from
    )
    app.state.profile_pdf_renderer = profile_pdf_renderer or FpdfProfileRenderer()
    app.state.clock = clock or SystemClock()
    app.state.seeds = seeds or SecureSeeds()
    acceptance_model = acceptance or NoAcceptanceModel()

    def selections(uow: SqlUnitOfWork) -> Selections:
        return Selections(
            uow,
            SqlNeeds(uow.session),
            SqlCandidatePool(uow.session),
            SqlSelections(uow.session),
            acceptance_model,
            app.state.clock,
            app.state.seeds,
            mechanics,
        )

    app.state.selections = selections

    install_error_handlers(app)
    app.include_router(auth_router)
    app.include_router(candidate_router)
    app.include_router(path_router)
    app.include_router(profile_router)
    app.include_router(employer_router)
    app.include_router(company_router)
    app.include_router(needs_router)
    app.include_router(selections_router)
    app.include_router(candidates_router)
    app.include_router(catalog_router)

    @app.get("/api/health", tags=["service"], summary="Проверка, что бэкенд жив")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
