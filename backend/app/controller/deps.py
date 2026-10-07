"""Порты для эндпоинтов: реализации кладёт в `app.state` сборка в `backend/main.py`. Контроллер
передаёт их в сценарий, сам время и seed не берёт."""

from typing import Annotated

from fastapi import Depends, Request

from app.db import UnitOfWorkDep
from app.usecase.interface import Clock, Mailer, ProfilePdfRenderer, SeedSource
from app.usecase.selection import Selections


def get_mailer(request: Request) -> Mailer:
    mailer: Mailer = request.app.state.mailer
    return mailer


def get_profile_pdf_renderer(request: Request) -> ProfilePdfRenderer:
    renderer: ProfilePdfRenderer = request.app.state.profile_pdf_renderer
    return renderer


def get_clock(request: Request) -> Clock:
    clock: Clock = request.app.state.clock
    return clock


def get_seeds(request: Request) -> SeedSource:
    seeds: SeedSource = request.app.state.seeds
    return seeds


def get_selections(request: Request, uow: UnitOfWorkDep) -> Selections:
    """Сценарии подборки на единице работы запроса."""
    selections: Selections = request.app.state.selections(uow)
    return selections


MailerDep = Annotated[Mailer, Depends(get_mailer)]
ProfilePdfRendererDep = Annotated[ProfilePdfRenderer, Depends(get_profile_pdf_renderer)]
ClockDep = Annotated[Clock, Depends(get_clock)]
SeedsDep = Annotated[SeedSource, Depends(get_seeds)]
SelectionsDep = Annotated[Selections, Depends(get_selections)]
