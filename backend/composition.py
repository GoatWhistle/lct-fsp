"""Общая проводка сценариев из портов — для обеих точек сборки (docs/adr/0001-layers-and-ports.md).

Прод (`main.py`) и стенд валидации (`validation/main.py`) только выбирают реализации портов и
передают их сюда; сценарии собираются здесь одинаково для обоих. Сценарий живёт на единице
работы: проводка отдаёт фабрики сценариев от неё, репозитории приходят фабриками от неё же.
Сценарии механик, подбора и разбора потребности из текста (`build_usecases`) нужны обоим;
сценарии кабинетов — учётки, ФСП ID, компании, потребностей, приглашений, справочников
(`build_platform_usecases`) — только проду.

Пакет стенда отсюда не импортируется — это проверяет тест на импорты.
"""

from collections.abc import Callable
from dataclasses import dataclass

from app.adapter.adaptive import MaxInformationSelector
from app.adapter.calibration import EloCalibration
from app.domain.bank.runner import CodeRunner
from app.usecase.account import Accounts, VerificationLinks
from app.usecase.attempt import CandidatePath
from app.usecase.calibration import AnswerCalibration
from app.usecase.catalog import CatalogQueries, CatalogSync
from app.usecase.company import Companies
from app.usecase.fsp import FspAccounts
from app.usecase.interface import (
    AcceptanceModel,
    AccountRepository,
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
    NeedReader,
    NeedRepository,
    PasswordHasher,
    SeedSource,
    SelectionRepository,
    SessionTokens,
    SkillModel,
    TextUnderstanding,
    UnitOfWork,
)
from app.usecase.invitation import Invitations
from app.usecase.need import Needs
from app.usecase.need_draft import NeedDrafts
from app.usecase.selection import Selections
from settings import Mechanics


def item_selector(mechanics: Mechanics) -> MaxInformationSelector:
    """Выбор задания с пулом и потолком показов из конфига механик."""
    return MaxInformationSelector(
        top_k=mechanics.exposure_top_k, max_rate=mechanics.exposure_max_rate
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
    )


@dataclass(frozen=True)
class Repositories[U: UnitOfWork]:
    """Фабрики репозиториев от единицы работы: репозиторий пишет в её транзакцию."""

    attempts: Callable[[U], AttemptRepository]
    fsp: Callable[[U], FspEvidenceReader]
    calibration: Callable[[U], CalibrationRepository]
    needs: Callable[[U], NeedReader]
    catalog: Callable[[U], CatalogRepository]
    pool: Callable[[U], CandidatePool]
    selections: Callable[[U], SelectionRepository]


@dataclass(frozen=True)
class Usecases[U: UnitOfWork]:
    """Фабрики сценариев от единицы работы."""

    calibration: Callable[[U], EloCalibration]
    candidate_path: Callable[[U], CandidatePath]
    answer_calibration: Callable[[U], AnswerCalibration]
    selections: Callable[[U], Selections]
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
            repositories.fsp(uow),
            calibration(uow),
            selector,
            skill_model,
            clock,
            seeds,
            code_runner,
            mechanics,
        )

    def answer_calibration(uow: U) -> AnswerCalibration:
        return AnswerCalibration(uow, calibration(uow))

    def selections(uow: U) -> Selections:
        return Selections(
            uow,
            repositories.needs(uow),
            repositories.catalog(uow),
            repositories.pool(uow),
            repositories.selections(uow),
            acceptance,
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

    return Usecases(calibration, candidate_path, answer_calibration, selections, need_drafts)


@dataclass(frozen=True)
class PlatformRepositories[U: UnitOfWork]:
    """Фабрики репозиториев кабинетов от единицы работы."""

    accounts: Callable[[U], AccountRepository]
    verifications: Callable[[U], EmailVerificationRepository]
    companies: Callable[[U], CompanyRepository]
    needs: Callable[[U], NeedRepository]
    catalog: Callable[[U], CatalogRepository]
    attempts: Callable[[U], AttemptRepository]
    fsp: Callable[[U], FspRepository]
    candidates: Callable[[U], CandidateRepository]
    invitations: Callable[[U], InvitationRepository]


@dataclass(frozen=True)
class PlatformUsecases[U: UnitOfWork]:
    """Фабрики сценариев кабинетов от единицы работы."""

    accounts: Callable[[U], Accounts]
    companies: Callable[[U], Companies]
    needs: Callable[[U], Needs]
    catalog: Callable[[U], CatalogQueries]
    fsp_accounts: Callable[[U], FspAccounts]
    invitations: Callable[[U], Invitations]


def build_platform_usecases[U: UnitOfWork](
    repositories: PlatformRepositories[U],
    *,
    mechanics: Mechanics,
    passwords: PasswordHasher,
    sessions: SessionTokens,
    mailer: Mailer,
    clock: Clock,
    links: VerificationLinks,
    skill_model: SkillModel,
    fsp_id: FspIdProvider,
    fsp_registry: FspRegistry,
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

    def fsp_accounts(uow: U) -> FspAccounts:
        return FspAccounts(
            uow,
            repositories.accounts(uow),
            repositories.attempts(uow),
            repositories.fsp(uow),
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
            repositories.candidates(uow),
            repositories.companies(uow),
            clock,
            weekly_budget=mechanics.invitation_weekly_budget,
            ttl_days=mechanics.invitation_ttl_days,
        )

    return PlatformUsecases(accounts, companies, needs, catalog, fsp_accounts, invitations)


def catalog_sync[U: UnitOfWork](
    catalog: Callable[[U], CatalogRepository], source: CatalogSource
) -> Callable[[U], CatalogSync]:
    """Синхронизация справочника из источника `source` — при старте бэкенда и из командной
    строки."""

    def sync(uow: U) -> CatalogSync:
        return CatalogSync(uow, catalog(uow), source)

    return sync
