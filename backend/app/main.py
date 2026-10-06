from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.assessment.path_router import router as path_router
from app.assessment.router import router as catalog_router
from app.cabinets import candidate_router, employer_router
from app.company.router import router as company_router
from app.config import Mechanics, Settings
from app.errors import install_error_handlers
from app.identity.router import router as auth_router
from app.mail import Mailer, SmtpMailer
from app.matching.router import router as needs_router

DESCRIPTION = """
Платформа подбора ИТ-специалистов с обратной механикой.

Ошибки приходят телом `{"code", "message"}`: `code` — для кода фронта, `message` — для
пользователя. Вход — cookie `access_token` (httpOnly), её ставит `POST /api/auth/login`.
Разделы `/api/candidate` и `/api/employer` доступны только своей роли.
"""


def create_app(
    settings: Settings | None = None,
    mechanics: Mechanics | None = None,
    mailer: Mailer | None = None,
) -> FastAPI:
    settings = settings or Settings()
    mechanics = mechanics or Mechanics.from_yaml(settings.mechanics_file)
    engine = create_engine(settings.database_url, pool_pre_ping=True)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        engine.dispose()

    app = FastAPI(
        title="Подбор ИТ-специалистов ФСП",
        description=DESCRIPTION,
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.engine = engine
    app.state.settings = settings
    app.state.mechanics = mechanics
    app.state.sessionmaker = sessionmaker(engine, expire_on_commit=False)
    app.state.mailer = mailer or SmtpMailer(
        settings.smtp_host, settings.smtp_port, settings.mail_from
    )

    install_error_handlers(app)
    app.include_router(auth_router)
    app.include_router(candidate_router)
    app.include_router(path_router)
    app.include_router(employer_router)
    app.include_router(company_router)
    app.include_router(needs_router)
    app.include_router(catalog_router)

    @app.get("/api/health", tags=["service"], summary="Проверка, что бэкенд жив")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
