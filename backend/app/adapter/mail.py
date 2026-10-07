"""Реализации порта `Mailer`: SMTP (локально — Mailpit) и запись в память для тестов."""

import logging
import smtplib
from email.message import EmailMessage

from app.domain.mail import Mail

log = logging.getLogger(__name__)


class SmtpMailer:
    def __init__(self, host: str, port: int, sender: str) -> None:
        self.host = host
        self.port = port
        self.sender = sender

    def send(self, mail: Mail) -> None:
        msg = EmailMessage()
        msg["From"] = self.sender
        msg["To"] = mail.to
        msg["Subject"] = mail.subject
        msg.set_content(mail.text)
        try:
            with smtplib.SMTP(self.host, self.port, timeout=10) as smtp:
                smtp.send_message(msg)
        except OSError:
            # Регистрация не должна падать из-за почты: письмо можно запросить повторно.
            log.exception("Не удалось отправить письмо на %s", mail.to)


class MemoryMailer:
    """Почта, которая никуда не уходит: письма копятся в `sent` по порядку отправки."""

    def __init__(self) -> None:
        self.sent: list[Mail] = []

    def send(self, mail: Mail) -> None:
        self.sent.append(mail)
