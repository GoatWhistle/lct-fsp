"""Порты для эндпоинтов: реализации кладёт в `app.state` сборка в `backend/main.py`."""

from typing import Annotated

from fastapi import Depends, Request

from app.usecase.interface import Mailer, ProfilePdfRenderer


def get_mailer(request: Request) -> Mailer:
    mailer: Mailer = request.app.state.mailer
    return mailer


def get_profile_pdf_renderer(request: Request) -> ProfilePdfRenderer:
    renderer: ProfilePdfRenderer = request.app.state.profile_pdf_renderer
    return renderer


MailerDep = Annotated[Mailer, Depends(get_mailer)]
ProfilePdfRendererDep = Annotated[ProfilePdfRenderer, Depends(get_profile_pdf_renderer)]
