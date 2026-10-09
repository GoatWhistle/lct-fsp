"""Письмо платформы; отправляет его порт `app.usecase.interface.Mailer`."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Mail:
    to: str
    subject: str
    text: str
    html: str | None = None
