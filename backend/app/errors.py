"""Ошибки API: машинный `code` для фронта и человеческое `message` по-русски.

Каждая ошибка — подкласс `AppError`. Эндпоинт перечисляет свои ошибки в
`responses=error_responses(...)`, и они попадают в OpenAPI вместе с кодами.
"""

from typing import Any, ClassVar

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


class ErrorOut(BaseModel):
    code: str = Field(description="Машинный код ошибки", examples=["invalid_credentials"])
    message: str = Field(
        description="Текст для пользователя", examples=["Неверный email или пароль"]
    )


class AppError(Exception):
    status_code: ClassVar[int] = 400
    code: ClassVar[str] = "bad_request"
    message: ClassVar[str] = "Некорректный запрос"

    def __init__(self) -> None:
        super().__init__(self.message)


def error_responses(*errors: type[AppError]) -> dict[int | str, dict[str, Any]]:
    """Ошибочные ответы для OpenAPI; ошибки с одним статусом сводятся в один ответ."""
    responses: dict[int | str, dict[str, Any]] = {}
    for error in errors:
        line = f"`{error.code}` — {error.message}"
        if error.status_code in responses:
            responses[error.status_code]["description"] += f"\n\n{line}"
        else:
            responses[error.status_code] = {"model": ErrorOut, "description": line}
    return responses


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        body = ErrorOut(code=exc.code, message=exc.message)
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())
