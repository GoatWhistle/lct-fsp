"""Сборка прода — вручную, без DI-контейнера (docs/adr/0001-layers-and-ports.md): здесь только
выбор реализаций портов, сценарии из них собирает общая проводка `composition`. Стенд валидации
собирается отдельно — `validation/main.py`.

На уровне модуля только определения функций: объект приложения строит
`uvicorn --factory main:create_app`, поэтому импорт `main` не читает конфиг и не открывает базу.
Новый роутер подключается в `create_app`. Синхронизация справочника — `sync_catalog`: её вызывают
и старт контейнера, и командная строка (`python -c 'import main; main.sync_catalog()'`).
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, closing
from datetime import timedelta

from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker

from app.adapter import irt
from app.adapter.acceptance import acceptance_model
from app.adapter.brand.mail_templates import BrandMailTemplates
from app.adapter.catalog_file import YamlCatalog
from app.adapter.clock import SystemClock
from app.adapter.code_runner import InProcessCodeRunner
from app.adapter.fsp_id import OidcFspId
from app.adapter.fsp_registry import FileFspRegistry
from app.adapter.mail import SmtpMailer
from app.adapter.password import Argon2Passwords
from app.adapter.profile_pdf import FpdfProfileRenderer
from app.adapter.resume_pdf import PypdfResumeText
from app.adapter.seed import SecureSeeds
from app.adapter.session import JwtSessions
from app.adapter.skill_cache import PROCESS_ENTRIES, PrefixCachedSkillModel
from app.adapter.text_llama import LlamaCompletion
from app.adapter.text_model import Completion
from app.adapter.text_rules import RulesTextUnderstanding, grade_hint_rule, load_synonyms
from app.controller.auth import router as auth_router
from app.controller.cabinets import candidate_router, employer_router
from app.controller.catalog import router as catalog_router
from app.controller.chat import router as chat_router
from app.controller.company import domain_router as company_domain_router
from app.controller.company import router as company_router
from app.controller.deps import SessionCookie
from app.controller.errors import install_error_handlers
from app.controller.feedback import router as feedback_router
from app.controller.fsp import candidate_router as fsp_router
from app.controller.fsp import router as fsp_auth_router
from app.controller.invitation import candidate_router as inbox_router
from app.controller.invitation import employer_router as invitations_router
from app.controller.jury import router as jury_router
from app.controller.need import router as needs_router
from app.controller.need import search_router as candidate_search_router
from app.controller.need import selections_router
from app.controller.path import router as path_router
from app.controller.profile import employer_router as candidates_router
from app.controller.profile import router as profile_router
from app.controller.regular_task import candidate_router as candidate_tasks_router
from app.controller.regular_task import employer_router as employer_tasks_router
from app.controller.vacancy import candidate_router as candidate_vacancies_router
from app.controller.vacancy import employer_router as employer_vacancies_router
from app.controller.vacancy_test import candidate_router as vacancy_test_inbox_router
from app.controller.vacancy_test import employer_router as vacancy_test_router
from app.domain.development_plan import DevelopmentPlan
from app.repository.account import SqlAccounts, SqlEmailVerifications
from app.repository.attempt import SqlAttemptRepository
from app.repository.calibration import SqlCalibrationRepository
from app.repository.candidate import SqlCandidateRepository
from app.repository.catalog import SqlCatalog
from app.repository.company import SqlCompanies
from app.repository.conversation import SqlMessages
from app.repository.database import create_db_engine
from app.repository.fsp import SqlFspRepository
from app.repository.invitation import SqlInvitations
from app.repository.need import SqlNeeds
from app.repository.regular_task import SqlRegularTasks
from app.repository.selection import SqlCandidatePool, SqlSelections
from app.repository.unit_of_work import SqlUnitOfWork
from app.repository.vacancy import SqlApplications, SqlVacancies
from app.repository.vacancy_test import SqlVacancyTests
from app.usecase.account import VerificationLinks
from app.usecase.chat import SearchChat
from app.usecase.development_plan import DevelopmentPlans
from app.usecase.interface import (
    AcceptanceModel,
    CandidateRepository,
    Clock,
    FspIdProvider,
    FspRegistry,
    Mailer,
    PasswordHasher,
    ProfilePdfRenderer,
    ResumeText,
    SeedSource,
    SkillModel,
    TextUnderstanding,
)
from composition import (
    PlatformRepositories,
    Repositories,
    build_platform_usecases,
    build_usecases,
    catalog_sync,
    experience_limits,
    item_selector,
    jury_mode,
    model_understanding,
    named_completion,
)
from settings import Mechanics, Settings


def description() -> str:
    """Описание API в OpenAPI."""
    return """
Платформа подбора ИТ-специалистов с обратной механикой.

Ошибки приходят телом `{"code", "message"}`: `code` — для кода фронта, `message` — для
пользователя. Вход — cookie `access_token` (httpOnly), её ставит `POST /api/auth/login`.
Разделы `/api/candidate` и `/api/employer` доступны только своей роли. Время — в UTC,
ISO 8601 с `Z`.
"""


def text_understanding(settings: Settings) -> TextUnderstanding:
    """Разбор текста по имени из настроек: `rules` — правила, `llama` — `llama-server` с откатом
    на правила по сбою и таймауту `text_understanding_timeout_seconds`; другое имя — модель,
    которую сборка находит по имени (`composition.named_completion`)."""
    synonyms = load_synonyms(settings.synonyms_file)
    timeout = settings.text_understanding_timeout_seconds
    complete: Completion
    match settings.text_understanding:
        case "rules":
            return RulesTextUnderstanding(synonyms)
        case "llama":
            complete = LlamaCompletion(settings.llama_url, settings.llama_model, timeout)
        case name:
            complete = named_completion(name, timeout)
    return model_understanding(complete, synonyms, timeout=timeout)


def plan_completion(settings: Settings) -> Completion | None:
    """Модель плана развития — та же, что у разбора текста; `rules` — модели нет, плана нет."""
    timeout = settings.text_understanding_timeout_seconds
    match settings.text_understanding:
        case "rules":
            return None
        case "llama":
            return LlamaCompletion(settings.llama_url, settings.llama_model, timeout)
        case name:
            return named_completion(name, timeout)


def create_app(
    settings: Settings | None = None,
    mechanics: Mechanics | None = None,
    mailer: Mailer | None = None,
    profile_pdf_renderer: ProfilePdfRenderer | None = None,
    clock: Clock | None = None,
    seeds: SeedSource | None = None,
    skill_model: SkillModel | None = None,
    acceptance: AcceptanceModel | None = None,
    passwords: PasswordHasher | None = None,
    understanding: TextUnderstanding | None = None,
    resume_text: ResumeText | None = None,
    fsp_id: FspIdProvider | None = None,
    fsp_registry: FspRegistry | None = None,
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
    app.state.mechanics = mechanics
    app.state.experience_limits = experience_limits(mechanics)
    session_factory = sessionmaker(engine)
    session_ttl = timedelta(hours=settings.session_ttl_hours)
    app.state.session_cookie = SessionCookie(
        max_age=int(session_ttl.total_seconds()), secure=settings.cookie_secure
    )

    def unit_of_work() -> SqlUnitOfWork:
        return SqlUnitOfWork(session_factory())

    def candidate_repository(uow: SqlUnitOfWork) -> CandidateRepository:
        return SqlCandidateRepository(
            uow.session, mechanics.grade_thresholds, mechanics.grade_confidence
        )

    def invitation_repository(uow: SqlUnitOfWork) -> SqlInvitations:
        return SqlInvitations(uow.session)

    app.state.unit_of_work = unit_of_work
    app.state.candidate_repository = candidate_repository
    app.state.invitation_repository = invitation_repository

    def application_repository(uow: SqlUnitOfWork) -> SqlApplications:
        return SqlApplications(uow.session)

    app.state.application_repository = application_repository
    app.state.profile_pdf_renderer = profile_pdf_renderer or FpdfProfileRenderer()
    app.state.clock = clock = clock or SystemClock()
    seeds = seeds or SecureSeeds()
    # Кэш префиксов один на приложение, приложение — одно на процесс.
    skill_model = skill_model or PrefixCachedSkillModel(irt, max_entries=PROCESS_ENTRIES)
    # Алгоритмы механики получают параметры конфига через конструктор —
    # tests/test_mechanics_config.py сверяет их с config/mechanics.yaml.
    app.state.item_selector = selector = item_selector(mechanics)

    understanding = understanding or text_understanding(settings)

    def attempts(uow: SqlUnitOfWork) -> SqlAttemptRepository:
        return SqlAttemptRepository(
            uow.session, mechanics.grade_thresholds, mechanics.grade_confidence
        )

    usecases = build_usecases(
        Repositories[SqlUnitOfWork](
            attempts=attempts,
            regular_tasks=lambda uow: SqlRegularTasks(uow.session),
            fsp=lambda uow: SqlFspRepository(uow.session),
            calibration=lambda uow: SqlCalibrationRepository(uow.session),
            needs=lambda uow: SqlNeeds(uow.session),
            catalog=lambda uow: SqlCatalog(uow.session),
            pool=lambda uow: SqlCandidatePool(uow.session),
            selections=lambda uow: SqlSelections(uow.session),
            vacancy_tests=lambda uow: SqlVacancyTests(uow.session),
        ),
        mechanics=mechanics,
        selector=selector,
        skill_model=skill_model,
        clock=clock,
        seeds=seeds,
        code_runner=InProcessCodeRunner(),
        acceptance=acceptance or acceptance_model(settings.acceptance_model_file),
        text_understanding=understanding,
    )
    app.state.calibration = usecases.calibration
    app.state.candidate_path = usecases.candidate_path
    app.state.answer_calibration = usecases.answer_calibration
    app.state.selections = usecases.selections
    app.state.profile_freshness = usecases.freshness
    app.state.need_drafts = usecases.need_drafts
    sessions = JwtSessions(settings.secret_key, session_ttl)
    platform = build_platform_usecases(
        PlatformRepositories[SqlUnitOfWork](
            accounts=lambda uow: SqlAccounts(uow.session),
            verifications=lambda uow: SqlEmailVerifications(uow.session),
            companies=lambda uow: SqlCompanies(uow.session),
            needs=lambda uow: SqlNeeds(uow.session),
            catalog=lambda uow: SqlCatalog(uow.session),
            regular_tasks=lambda uow: SqlRegularTasks(uow.session),
            attempts=attempts,
            fsp=lambda uow: SqlFspRepository(uow.session),
            candidates=candidate_repository,
            invitations=invitation_repository,
            messages=lambda uow: SqlMessages(uow.session),
            selections=lambda uow: SqlSelections(uow.session),
            calibration=lambda uow: SqlCalibrationRepository(uow.session),
            vacancies=lambda uow: SqlVacancies(uow.session),
            applications=application_repository,
            vacancy_tests=lambda uow: SqlVacancyTests(uow.session),
        ),
        mechanics=mechanics,
        passwords=passwords or Argon2Passwords(),
        sessions=sessions,
        mailer=mailer or SmtpMailer(settings.smtp_host, settings.smtp_port, settings.mail_from),
        mail_templates=BrandMailTemplates(),
        clock=clock,
        links=VerificationLinks(settings.frontend_url, settings.email_token_ttl_hours),
        skill_model=skill_model,
        fsp_id=fsp_id
        or OidcFspId(
            issuer=settings.fsp_id_issuer,
            server_url=settings.fsp_id_server_url,
            client_id=settings.fsp_id_client_id,
            client_secret=settings.fsp_id_client_secret,
            redirect_uri=settings.fsp_id_callback,
        ),
        fsp_registry=fsp_registry or FileFspRegistry(settings.fsp_registry_path),
        resume_text=resume_text
        or PypdfResumeText(
            max_pages=mechanics.resume_max_pages,
            max_content_bytes=mechanics.resume_max_content_bytes,
            min_font_pt=mechanics.resume_min_font_pt,
            max_lightness=mechanics.resume_max_lightness,
        ),
        text_understanding=understanding,
        grade_hints=grade_hint_rule(load_synonyms(settings.synonyms_file)),
        seeds=seeds,
        code_runner=InProcessCodeRunner(),
    )
    app.state.accounts = platform.accounts
    app.state.jury = jury_mode(
        lambda uow: SqlAccounts(uow.session),
        usecases,
        platform,
        sessions=sessions,
        clock=clock,
        enabled=settings.demo_mode,
    )
    app.state.companies = platform.companies
    app.state.needs = platform.needs
    app.state.catalog = platform.catalog
    app.state.regular_tasks = platform.regular_tasks
    app.state.fsp_accounts = platform.fsp_accounts
    app.state.frontend_url = settings.frontend_url
    app.state.invitations = platform.invitations
    app.state.conversations = platform.conversations
    app.state.feedback = platform.feedback
    app.state.search_chat = lambda uow: SearchChat(
        usecases.need_drafts(uow),
        usecases.selections(uow),
        plan_completion(settings),
        timeout=settings.text_understanding_timeout_seconds,
    )
    plans_cache: dict[tuple[uuid.UUID, str], DevelopmentPlan | None] = {}
    plan_model = plan_completion(settings)
    app.state.development_plans = lambda uow: DevelopmentPlans(
        platform.feedback(uow),
        plan_model,
        timeout=settings.text_understanding_timeout_seconds,
        cache=plans_cache,
    )
    app.state.resume_drafts = platform.resume_drafts
    app.state.vacancies = platform.vacancies
    app.state.vacancy_tests = platform.vacancy_tests
    app.state.applications = platform.applications

    install_error_handlers(app)
    app.include_router(auth_router)
    app.include_router(jury_router)
    app.include_router(fsp_auth_router)
    app.include_router(fsp_router)
    app.include_router(candidate_router)
    app.include_router(path_router)
    app.include_router(profile_router)
    app.include_router(employer_router)
    app.include_router(company_router)
    app.include_router(company_domain_router)
    app.include_router(needs_router)
    app.include_router(selections_router)
    app.include_router(candidate_search_router)
    app.include_router(candidates_router)
    app.include_router(employer_tasks_router)
    app.include_router(candidate_tasks_router)
    app.include_router(invitations_router)
    app.include_router(inbox_router)
    app.include_router(vacancy_test_router)
    app.include_router(vacancy_test_inbox_router)
    app.include_router(employer_vacancies_router)
    app.include_router(candidate_vacancies_router)
    app.include_router(feedback_router)
    app.include_router(chat_router)
    app.include_router(catalog_router)

    @app.get("/api/health", tags=["service"], summary="Проверка, что бэкенд жив")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


def sync_catalog(settings: Settings | None = None) -> None:
    """Справочники из `config/catalog.yaml` в базу. Идемпотентна: повторный запуск справочник
    не дублирует."""
    settings = settings or Settings()
    engine = create_db_engine(settings.database_url)

    def catalog(uow: SqlUnitOfWork) -> SqlCatalog:
        return SqlCatalog(uow.session)

    try:
        sync = catalog_sync(catalog, YamlCatalog(settings.catalog_file))
        with closing(SqlUnitOfWork(Session(engine))) as uow:
            sync(uow).run()
    finally:
        engine.dispose()
    print("Справочники синхронизированы")
