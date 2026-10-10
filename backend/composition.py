"""Общая проводка сценариев из портов — для обеих точек сборки (docs/adr/0001-layers-and-ports.md).

Прод (`main.py`) и стенд валидации (`validation/main.py`) только выбирают реализации портов и
передают их сюда; сценарии собираются здесь одинаково для обоих. Сценарий живёт на единице
работы: проводка отдаёт фабрики сценариев от неё, репозитории приходят фабриками от неё же.
Сценарии механик, подбора и разбора потребности из текста (`build_usecases`) нужны обоим;
сценарии кабинетов — учётки, ФСП ID, компании, потребностей, приглашений, вакансий и откликов,
справочников, регулярных заданий, обратной связи кандидату (`build_platform_usecases`) — только
проду.

Пакет стенда отсюда не импортируется — это проверяет тест на импорты.
"""

import importlib
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial

from app.adapter.adaptive import MaxInformationSelector
from app.adapter.calibration import EloCalibration
from app.adapter.drift import CusumDriftDetector
from app.adapter.text_model import Completion, ModelTextUnderstanding, WithFallback
from app.adapter.text_rules import RulesTextUnderstanding, Synonyms
from app.domain.bank.runner import CodeRunner
from app.domain.experience import ExperienceLimits
from app.domain.resume_draft import GradeHintRule
from app.usecase.account import Accounts, VerificationLinks
from app.usecase.attempt import CandidatePath
from app.usecase.calibration import AnswerCalibration
from app.usecase.catalog import CatalogQueries, CatalogSync
from app.usecase.company import Companies
from app.usecase.conversation import Conversations
from app.usecase.feedback import CandidateFeedback
from app.usecase.fsp import FspAccounts
from app.usecase.interface import (
    AcceptanceModel,
    AccountRepository,
    ApplicationRepository,
    AttemptRepository,
    CalibrationRepository,
    CandidatePool,
    CandidateRepository,
    CatalogRepository,
    CatalogSource,
    Clock,
    CompanyRepository,
    EmailVerificationRepository,
    FspEvidenceReader,
    FspIdProvider,
    FspRegistry,
    FspRepository,
    InvitationRepository,
    ItemSelector,
    Mailer,
    MailTemplates,
    MessageRepository,
    NeedReader,
    NeedRepository,
    PasswordHasher,
    RegularTaskReader,
    RegularTaskRepository,
    ResumeText,
    SeedSource,
    SelectionRepository,
    SessionTokens,
    SkillModel,
    TextUnderstanding,
    UnitOfWork,
    VacancyRepository,
    VacancyTestReader,
    VacancyTestRepository,
)
from app.usecase.invitation import Invitations
from app.usecase.jury import JuryMode
from app.usecase.need import Needs
from app.usecase.need_draft import NeedDrafts
from app.usecase.regular_task import RegularTasks
from app.usecase.resume_draft import ResumeDrafts
from app.usecase.selection import Selections
from app.usecase.skill_profile import ProfileFreshness
from app.usecase.vacancy import Applications, Vacancies
from app.usecase.vacancy_test import VacancyTests, plan_of_need
from settings import Mechanics

# Пакет моделей разбора текста, которые собираются только по имени: модуль `<пакет>.<имя>` с
# функцией `completion(timeout: float) -> Completion`. Пакета может не быть — тогда есть только
# правила и llama.
NAMED_MODELS = "app.adapter.demo"


def item_selector(mechanics: Mechanics) -> MaxInformationSelector:
    """Выбор задания с пулом и потолком показов из конфига механик."""
    return MaxInformationSelector(
        top_k=mechanics.exposure_top_k, max_rate=mechanics.exposure_max_rate
    )


def model_understanding(
    complete: Completion, synonyms: Synonyms, *, timeout: float
) -> TextUnderstanding:
    """Разбор моделью за `complete` с откатом на правила того же словаря: сбой или ответ позже
    `timeout` секунд — черновик правил в том же запросе."""
    model = ModelTextUnderstanding(complete, list(synonyms.cities), synonyms.experience_years)
    return WithFallback(model, RulesTextUnderstanding(synonyms), timeout=timeout)


def named_completion(name: str, timeout: float) -> Completion:
    """Модель из пакета `NAMED_MODELS` по имени из окружения — без прямого импорта. Нет модуля —
    понятная ошибка сборки, а не падение на первом запросе."""
    unknown = f"неизвестный разбор текста {name!r}: есть rules и llama"
    module_name = f"{NAMED_MODELS}.{name}"
    # Тесты и служебные модули пакета — не модели: их сборка не импортирует.
    if not name.isidentifier() or name.startswith(("_", "test")):
        raise ValueError(unknown)
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        if e.name not in {NAMED_MODELS, module_name}:
            raise
        raise ValueError(unknown) from e
    completion: Callable[[float], Completion] | None = getattr(module, "completion", None)
    if completion is None:
        raise ValueError(unknown)
    return completion(timeout)


def experience_limits(mechanics: Mechanics) -> ExperienceLimits:
    return ExperienceLimits(
        entries_max=mechanics.experience_entries_max,
        line_max=mechanics.experience_line_max,
        summary_max=mechanics.experience_summary_max,
        stack_max=mechanics.experience_stack_max,
    )


def elo_calibration(repository: CalibrationRepository, mechanics: Mechanics) -> EloCalibration:
    """Калибровка Эло с параметрами из конфига механик — tests/test_mechanics_config.py сверяет
    их с config/mechanics.yaml."""
    return EloCalibration(
        repository,
        expert_discrimination=mechanics.expert_discrimination,
        expert_difficulty_by_grade=mechanics.expert_difficulty_by_grade,
        elo_k_initial=mechanics.elo_k_initial,
        elo_k_half_responses=mechanics.elo_k_half_responses,
        elo_k_min=mechanics.elo_k_min,
        calibration_refit_min_responses=mechanics.calibration_refit_min_responses,
        calibration_expert_gap_review=mechanics.calibration_expert_gap_review,
        calibration_refit_difficulty_prior_sd=mechanics.calibration_refit_difficulty_prior_sd,
        calibration_refit_log_discrimination_prior_sd=(
            mechanics.calibration_refit_log_discrimination_prior_sd
        ),
        calibration_link_window_attempts=mechanics.calibration_link_window_attempts,
        item_fit_groups=mechanics.item_fit_groups,
        item_fit_rmsd_max=mechanics.item_fit_rmsd_max,
        item_fit_discrimination_min=mechanics.item_fit_discrimination_min,
        item_fit_ceiling_gain_max=mechanics.item_fit_ceiling_gain_max,
        item_fit_ceiling_min=mechanics.item_fit_ceiling_min,
        item_fit_ceiling_step=mechanics.item_fit_ceiling_step,
    )


def drift_detector(repository: CalibrationRepository, mechanics: Mechanics) -> CusumDriftDetector:
    """Детектор дрейфа с параметрами из конфига механик."""
    return CusumDriftDetector(
        repository, drift_shift=mechanics.drift_shift, drift_cusum_h=mechanics.drift_cusum_h
    )


@dataclass(frozen=True)
class Repositories[U: UnitOfWork]:
    """Фабрики репозиториев от единицы работы: репозиторий пишет в её транзакцию."""

    attempts: Callable[[U], AttemptRepository]
    regular_tasks: Callable[[U], RegularTaskReader]
    fsp: Callable[[U], FspEvidenceReader]
    calibration: Callable[[U], CalibrationRepository]
    needs: Callable[[U], NeedReader]
    catalog: Callable[[U], CatalogRepository]
    pool: Callable[[U], CandidatePool]
    selections: Callable[[U], SelectionRepository]
    # Планы тестов по вакансии — у прода; стенд валидации их не заводит.
    vacancy_tests: Callable[[U], VacancyTestReader] | None = None


@dataclass(frozen=True)
class Usecases[U: UnitOfWork]:
    """Фабрики сценариев от единицы работы и доворот профиля навыков до «сейчас» — он единицы
    работы не требует."""

    calibration: Callable[[U], EloCalibration]
    candidate_path: Callable[[U], CandidatePath]
    answer_calibration: Callable[[U], AnswerCalibration]
    selections: Callable[[U], Selections]
    freshness: ProfileFreshness
    need_drafts: Callable[[U], NeedDrafts]


def build_usecases[U: UnitOfWork](
    repositories: Repositories[U],
    *,
    mechanics: Mechanics,
    selector: ItemSelector,
    skill_model: SkillModel,
    clock: Clock,
    seeds: SeedSource,
    code_runner: CodeRunner,
    acceptance: AcceptanceModel,
    text_understanding: TextUnderstanding,
) -> Usecases[U]:
    def calibration(uow: U) -> EloCalibration:
        return elo_calibration(repositories.calibration(uow), mechanics)

    def candidate_path(uow: U) -> CandidatePath:
        return CandidatePath(
            uow,
            repositories.attempts(uow),
            repositories.regular_tasks(uow),
            repositories.fsp(uow),
            calibration(uow),
            selector,
            skill_model,
            clock,
            seeds,
            code_runner,
            mechanics,
            repositories.vacancy_tests(uow) if repositories.vacancy_tests else None,
        )

    def answer_calibration(uow: U) -> AnswerCalibration:
        return AnswerCalibration(
            uow, calibration(uow), drift_detector(repositories.calibration(uow), mechanics)
        )

    def selections(uow: U) -> Selections:
        return Selections(
            uow,
            repositories.needs(uow),
            repositories.catalog(uow),
            repositories.pool(uow),
            repositories.selections(uow),
            acceptance,
            skill_model,
            clock,
            seeds,
            mechanics,
        )

    def need_drafts(uow: U) -> NeedDrafts:
        return NeedDrafts(
            uow,
            repositories.catalog(uow),
            text_understanding,
            confident=mechanics.need_draft_confident,
        )

    return Usecases(
        calibration,
        candidate_path,
        answer_calibration,
        selections,
        ProfileFreshness(skill_model, mechanics),
        need_drafts,
    )


@dataclass(frozen=True)
class PlatformRepositories[U: UnitOfWork]:
    """Фабрики репозиториев кабинетов от единицы работы."""

    accounts: Callable[[U], AccountRepository]
    verifications: Callable[[U], EmailVerificationRepository]
    companies: Callable[[U], CompanyRepository]
    needs: Callable[[U], NeedRepository]
    catalog: Callable[[U], CatalogRepository]
    regular_tasks: Callable[[U], RegularTaskRepository]
    attempts: Callable[[U], AttemptRepository]
    fsp: Callable[[U], FspRepository]
    candidates: Callable[[U], CandidateRepository]
    invitations: Callable[[U], InvitationRepository]
    messages: Callable[[U], MessageRepository]
    selections: Callable[[U], SelectionRepository]
    calibration: Callable[[U], CalibrationRepository]
    vacancies: Callable[[U], VacancyRepository]
    applications: Callable[[U], ApplicationRepository]
    vacancy_tests: Callable[[U], VacancyTestRepository]


@dataclass(frozen=True)
class PlatformUsecases[U: UnitOfWork]:
    """Фабрики сценариев кабинетов от единицы работы."""

    accounts: Callable[[U], Accounts]
    companies: Callable[[U], Companies]
    needs: Callable[[U], Needs]
    catalog: Callable[[U], CatalogQueries]
    regular_tasks: Callable[[U], RegularTasks]
    fsp_accounts: Callable[[U], FspAccounts]
    invitations: Callable[[U], Invitations]
    conversations: Callable[[U], Conversations]
    feedback: Callable[[U], CandidateFeedback]
    resume_drafts: Callable[[U], ResumeDrafts]
    vacancies: Callable[[U], Vacancies]
    applications: Callable[[U], Applications]
    vacancy_tests: Callable[[U], VacancyTests]


def build_platform_usecases[U: UnitOfWork](
    repositories: PlatformRepositories[U],
    *,
    mechanics: Mechanics,
    passwords: PasswordHasher,
    sessions: SessionTokens,
    mailer: Mailer,
    mail_templates: MailTemplates,
    clock: Clock,
    links: VerificationLinks,
    skill_model: SkillModel,
    fsp_id: FspIdProvider,
    fsp_registry: FspRegistry,
    resume_text: ResumeText,
    text_understanding: TextUnderstanding,
    grade_hints: GradeHintRule,
    seeds: SeedSource,
    code_runner: CodeRunner,
) -> PlatformUsecases[U]:
    def accounts(uow: U) -> Accounts:
        return Accounts(
            uow,
            repositories.accounts(uow),
            repositories.verifications(uow),
            passwords,
            sessions,
            mailer,
            clock,
            links,
            mail_templates,
        )

    def companies(uow: U) -> Companies:
        return Companies(uow, repositories.companies(uow), repositories.catalog(uow), clock)

    def needs(uow: U) -> Needs:
        return Needs(
            uow,
            repositories.needs(uow),
            repositories.catalog(uow),
            clock,
            key_min_technologies=mechanics.need_key_topic_min_technologies,
        )

    def catalog(uow: U) -> CatalogQueries:
        return CatalogQueries(uow, repositories.catalog(uow))

    def regular_tasks(uow: U) -> RegularTasks:
        return RegularTasks(
            uow,
            repositories.regular_tasks(uow),
            repositories.attempts(uow),
            repositories.catalog(uow),
            repositories.companies(uow),
            repositories.fsp(uow),
            skill_model,
            clock,
            mechanics,
        )

    def fsp_accounts(uow: U) -> FspAccounts:
        return FspAccounts(
            uow,
            repositories.accounts(uow),
            repositories.attempts(uow),
            repositories.fsp(uow),
            repositories.regular_tasks(uow),
            fsp_id,
            fsp_registry,
            sessions,
            skill_model,
            clock,
            mechanics,
        )

    def invitations(uow: U) -> Invitations:
        return Invitations(
            uow,
            repositories.invitations(uow),
            repositories.applications(uow),
            repositories.candidates(uow),
            repositories.companies(uow),
            clock,
            weekly_budget=mechanics.invitation_weekly_budget,
            ttl_days=mechanics.invitation_ttl_days,
            needs=repositories.needs(uow),
            vacancy_tests=repositories.vacancy_tests(uow),
            test_plan=partial(plan_of_need, mechanics=mechanics),
        )

    def vacancy_tests(uow: U) -> VacancyTests:
        return VacancyTests(
            uow,
            repositories.needs(uow),
            repositories.vacancy_tests(uow),
            repositories.invitations(uow),
            repositories.attempts(uow),
            elo_calibration(repositories.calibration(uow), mechanics),
            skill_model,
            clock,
            seeds,
            code_runner,
            mechanics,
        )

    def conversations(uow: U) -> Conversations:
        return Conversations(
            uow,
            repositories.invitations(uow),
            repositories.messages(uow),
            clock,
            max_length=mechanics.message_max_length,
        )

    def feedback(uow: U) -> CandidateFeedback:
        return CandidateFeedback(
            uow,
            repositories.candidates(uow),
            repositories.selections(uow),
            repositories.attempts(uow),
            repositories.regular_tasks(uow),
            repositories.fsp(uow),
            elo_calibration(repositories.calibration(uow), mechanics),
            skill_model,
            clock,
            mechanics,
        )

    def resume_drafts(uow: U) -> ResumeDrafts:
        return ResumeDrafts(
            uow,
            repositories.catalog(uow),
            repositories.candidates(uow),
            resume_text,
            text_understanding,
            clock,
            rule=grade_hints,
            max_bytes=mechanics.resume_max_bytes,
            confident=mechanics.resume_draft_confident,
            experience_limits=experience_limits(mechanics),
        )

    def vacancies(uow: U) -> Vacancies:
        return Vacancies(
            uow,
            repositories.vacancies(uow),
            repositories.companies(uow),
            repositories.catalog(uow),
            clock,
        )

    def applications(uow: U) -> Applications:
        return Applications(
            uow,
            repositories.applications(uow),
            repositories.vacancies(uow),
            repositories.invitations(uow),
            repositories.candidates(uow),
            clock,
            ttl_days=mechanics.invitation_ttl_days,
        )

    return PlatformUsecases(
        accounts,
        companies,
        needs,
        catalog,
        regular_tasks,
        fsp_accounts,
        invitations,
        conversations,
        feedback,
        resume_drafts,
        vacancies,
        applications,
        vacancy_tests,
    )


def catalog_sync[U: UnitOfWork](
    catalog: Callable[[U], CatalogRepository], source: CatalogSource
) -> Callable[[U], CatalogSync]:
    """Синхронизация справочника из источника `source` — при старте бэкенда и из командной
    строки."""

    def sync(uow: U) -> CatalogSync:
        return CatalogSync(uow, catalog(uow), source)

    return sync


def jury_mode[U: UnitOfWork](
    accounts: Callable[[U], AccountRepository],
    usecases: Usecases[U],
    platform: PlatformUsecases[U],
    *,
    sessions: SessionTokens,
    clock: Clock,
    enabled: bool,
) -> Callable[[U], JuryMode]:
    """Режим жюри из сценариев кабинетов и пути кандидата; `enabled` — настройка окружения."""

    def jury(uow: U) -> JuryMode:
        return JuryMode(
            uow,
            accounts(uow),
            platform.companies(uow),
            platform.needs(uow),
            usecases.selections(uow),
            usecases.candidate_path(uow),
            sessions,
            clock,
            enabled=enabled,
        )

    return jury
