"""Зависимости эндпоинтов: единица работы запроса, сценарии на ней, порты и текущий пользователь.

Реализации и фабрики сценариев кладёт в `app.state` сборка в `backend/main.py`. Контроллер
передаёт порты в сценарий, сам время и seed не берёт. Права проверяет только бэкенд — фронт лишь
прячет кнопки: разделы одной роли — роутер с `dependencies=role_guard(Role.x)` и префиксом
`/api/candidate` или `/api/employer`; пользователь в эндпоинте — `CurrentUser`.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, Request, params
from fastapi.security import APIKeyCookie

from app.controller.errors import error_responses
from app.domain.account import Account, Role
from app.domain.errors import NotAuthenticated, WrongRole
from app.usecase.account import Accounts
from app.usecase.attempt import CandidatePath
from app.usecase.calibration import AnswerCalibration
from app.usecase.catalog import CatalogQueries
from app.usecase.company import Companies
from app.usecase.conversation import Conversations
from app.usecase.feedback import CandidateFeedback
from app.usecase.fsp import FspAccounts
from app.usecase.interface import (
    CandidateRepository,
    Clock,
    InvitationReader,
    ProfilePdfRenderer,
    RequestUnitOfWork,
)
from app.usecase.invitation import Invitations
from app.usecase.need import Needs
from app.usecase.need_draft import NeedDrafts
from app.usecase.regular_task import RegularTasks
from app.usecase.selection import Selections
from app.usecase.skill_profile import ProfileFreshness
from settings import Mechanics

ACCESS_COOKIE = "access_token"


@dataclass(frozen=True)
class SessionCookie:
    """Cookie входа: срок в секундах и флаг `Secure` — из настроек стенда."""

    max_age: int
    secure: bool


def get_unit_of_work(request: Request) -> Iterator[RequestUnitOfWork]:
    """Единица работы запроса; фабрику собирает `create_app`. Транзакции — блоки `with uow:`
    в сценариях, соединение освобождается в конце запроса."""
    uow: RequestUnitOfWork = request.app.state.unit_of_work()
    try:
        yield uow
    finally:
        uow.close()


UnitOfWorkDep = Annotated[RequestUnitOfWork, Depends(get_unit_of_work)]


def get_mechanics(request: Request) -> Mechanics:
    mechanics: Mechanics = request.app.state.mechanics
    return mechanics


def get_session_cookie(request: Request) -> SessionCookie:
    cookie: SessionCookie = request.app.state.session_cookie
    return cookie


def get_profile_pdf_renderer(request: Request) -> ProfilePdfRenderer:
    renderer: ProfilePdfRenderer = request.app.state.profile_pdf_renderer
    return renderer


def get_clock(request: Request) -> Clock:
    clock: Clock = request.app.state.clock
    return clock


def get_profile_freshness(request: Request) -> ProfileFreshness:
    freshness: ProfileFreshness = request.app.state.profile_freshness
    return freshness


def get_frontend_url(request: Request) -> str:
    """Адрес фронта — куда бэкенд возвращает браузер после ФСП ID."""
    url: str = request.app.state.frontend_url
    return url


MechanicsDep = Annotated[Mechanics, Depends(get_mechanics)]
SessionCookieDep = Annotated[SessionCookie, Depends(get_session_cookie)]
ProfilePdfRendererDep = Annotated[ProfilePdfRenderer, Depends(get_profile_pdf_renderer)]
ClockDep = Annotated[Clock, Depends(get_clock)]
ProfileFreshnessDep = Annotated[ProfileFreshness, Depends(get_profile_freshness)]
FrontendUrlDep = Annotated[str, Depends(get_frontend_url)]


def get_accounts(request: Request, uow: UnitOfWorkDep) -> Accounts:
    """Сценарии учётки на единице работы запроса."""
    accounts: Accounts = request.app.state.accounts(uow)
    return accounts


def get_fsp_accounts(request: Request, uow: UnitOfWorkDep) -> FspAccounts:
    fsp_accounts: FspAccounts = request.app.state.fsp_accounts(uow)
    return fsp_accounts


def get_catalog(request: Request, uow: UnitOfWorkDep) -> CatalogQueries:
    catalog: CatalogQueries = request.app.state.catalog(uow)
    return catalog


def get_companies(request: Request, uow: UnitOfWorkDep) -> Companies:
    companies: Companies = request.app.state.companies(uow)
    return companies


def get_needs(request: Request, uow: UnitOfWorkDep) -> Needs:
    needs: Needs = request.app.state.needs(uow)
    return needs


def get_regular_tasks(request: Request, uow: UnitOfWorkDep) -> RegularTasks:
    tasks: RegularTasks = request.app.state.regular_tasks(uow)
    return tasks


def get_selections(request: Request, uow: UnitOfWorkDep) -> Selections:
    selections: Selections = request.app.state.selections(uow)
    return selections


def get_need_drafts(request: Request, uow: UnitOfWorkDep) -> NeedDrafts:
    drafts: NeedDrafts = request.app.state.need_drafts(uow)
    return drafts


def get_invitations(request: Request, uow: UnitOfWorkDep) -> Invitations:
    invitations: Invitations = request.app.state.invitations(uow)
    return invitations


def get_conversations(request: Request, uow: UnitOfWorkDep) -> Conversations:
    conversations: Conversations = request.app.state.conversations(uow)
    return conversations


def get_feedback(request: Request, uow: UnitOfWorkDep) -> CandidateFeedback:
    feedback: CandidateFeedback = request.app.state.feedback(uow)
    return feedback


def get_candidate_path(request: Request, uow: UnitOfWorkDep) -> CandidatePath:
    paths: CandidatePath = request.app.state.candidate_path(uow)
    return paths


def get_answer_calibration(request: Request, uow: UnitOfWorkDep) -> AnswerCalibration:
    """Калибровка после ответа — на той же единице работы запроса, своим блоком после ответа."""
    calibrations: AnswerCalibration = request.app.state.answer_calibration(uow)
    return calibrations


def get_candidates(request: Request, uow: UnitOfWorkDep) -> CandidateRepository:
    """Репозиторий кандидатов на единице работы запроса."""
    candidates: CandidateRepository = request.app.state.candidate_repository(uow)
    return candidates


def get_invitation_reader(request: Request, uow: UnitOfWorkDep) -> InvitationReader:
    """Приглашения для правила раскрытия на единице работы запроса."""
    reader: InvitationReader = request.app.state.invitation_repository(uow)
    return reader


AccountsDep = Annotated[Accounts, Depends(get_accounts)]
FspAccountsDep = Annotated[FspAccounts, Depends(get_fsp_accounts)]
CatalogQueriesDep = Annotated[CatalogQueries, Depends(get_catalog)]
CompaniesDep = Annotated[Companies, Depends(get_companies)]
NeedsDep = Annotated[Needs, Depends(get_needs)]
SelectionsDep = Annotated[Selections, Depends(get_selections)]
RegularTasksDep = Annotated[RegularTasks, Depends(get_regular_tasks)]
NeedDraftsDep = Annotated[NeedDrafts, Depends(get_need_drafts)]
CandidatePathDep = Annotated[CandidatePath, Depends(get_candidate_path)]
AnswerCalibrationDep = Annotated[AnswerCalibration, Depends(get_answer_calibration)]
CandidatesDep = Annotated[CandidateRepository, Depends(get_candidates)]
InvitationsDep = Annotated[Invitations, Depends(get_invitations)]
ConversationsDep = Annotated[Conversations, Depends(get_conversations)]
FeedbackDep = Annotated[CandidateFeedback, Depends(get_feedback)]
InvitationReaderDep = Annotated[InvitationReader, Depends(get_invitation_reader)]

_cookie_scheme = APIKeyCookie(
    name=ACCESS_COOKIE,
    scheme_name="session",
    auto_error=False,
    description="httpOnly-cookie; ставит `POST /api/auth/login`, снимает `POST /api/auth/logout`",
)


def get_current_user(
    accounts: AccountsDep, access_token: Annotated[str | None, Depends(_cookie_scheme)]
) -> Account:
    return accounts.session_account(access_token)


CurrentUser = Annotated[Account, Depends(get_current_user)]


def get_optional_user(
    accounts: AccountsDep, access_token: Annotated[str | None, Depends(_cookie_scheme)]
) -> Account | None:
    """Пользователь, если вошёл; аноним — `None`."""
    try:
        return accounts.session_account(access_token)
    except NotAuthenticated:
        return None


OptionalUser = Annotated[Account | None, Depends(get_optional_user)]

AUTH_RESPONSES = error_responses(NotAuthenticated)


def require_role(role: Role) -> Callable[[Account], Account]:
    def check(user: CurrentUser) -> Account:
        if user.role != role:
            raise WrongRole()
        return user

    return check


def role_guard(role: Role) -> list[params.Depends]:
    return [Depends(require_role(role))]


ROLE_RESPONSES: dict[int | str, dict[str, Any]] = error_responses(NotAuthenticated, WrongRole)
