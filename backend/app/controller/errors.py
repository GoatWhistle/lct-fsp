"""Доменные ошибки в HTTP: статус по таблице, тело `{"code", "message"}`.

Эндпоинт перечисляет свои ошибки в `responses=error_responses(...)`, и они попадают в OpenAPI
вместе с кодами. Ошибка без своей строки в `STATUS` получает статус ближайшего предка.
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.domain import errors as e

STATUS: dict[type[e.DomainError], int] = {
    e.DomainError: 400,
    e.NotAuthenticated: 401,
    e.WrongRole: 403,
    e.EmailTaken: 409,
    e.TokenInvalid: 400,
    e.TokenExpired: 400,
    e.InvalidCredentials: 401,
    e.EmailNotVerified: 403,
    e.SpecializationNotFound: 404,
    e.UnknownIndustry: 422,
    e.UnknownSpecialization: 422,
    e.UnknownGrade: 422,
    e.UnknownTechnology: 422,
    e.SpecializationWithoutTest: 422,
    e.StepUnavailable: 409,
    e.GradeNotOffered: 409,
    e.NoTestInProgress: 409,
    e.ItemNotCurrent: 409,
    e.ProfileNotFound: 404,
    e.CandidateNotFound: 404,
    e.CityRequired: 422,
    e.NeedNotFound: 404,
    e.TopicNotInSpecialization: 422,
    e.InvalidSalaryRange: 422,
    e.SelectionNotFound: 404,
}


class ErrorOut(BaseModel):
    code: str = Field(description="Машинный код ошибки", examples=["invalid_credentials"])
    message: str = Field(
        description="Текст для пользователя", examples=["Неверный email или пароль"]
    )


def status_of(error: type[e.DomainError]) -> int:
    """Статус ближайшего предка в таблице: подкласс без своей строки наследует статус."""
    return next(STATUS[cls] for cls in error.__mro__ if cls in STATUS)


def error_responses(*errors: type[e.DomainError]) -> dict[int | str, dict[str, Any]]:
    """Ошибочные ответы для OpenAPI; ошибки с одним статусом сводятся в один ответ."""
    responses: dict[int | str, dict[str, Any]] = {}
    for error in errors:
        status = status_of(error)
        line = f"`{error.code}` — {error.message}"
        if status in responses:
            responses[status]["description"] += f"\n\n{line}"
        else:
            responses[status] = {"model": ErrorOut, "description": line}
    return responses


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(e.DomainError)
    async def handle_domain_error(_: Request, exc: e.DomainError) -> JSONResponse:
        body = ErrorOut(code=exc.code, message=exc.message)
        return JSONResponse(status_code=status_of(type(exc)), content=body.model_dump())
