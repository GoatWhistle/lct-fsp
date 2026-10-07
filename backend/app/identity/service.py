from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.domain.errors import (
    EmailNotVerified,
    EmailTaken,
    InvalidCredentials,
    NotAuthenticated,
    TokenExpired,
    TokenInvalid,
)
from app.domain.mail import Mail
from app.identity import security
from app.identity.models import EmailVerificationToken, Role, User
from app.usecase.interface import Clock, Mailer


def register(
    db: Session,
    mailer: Mailer,
    settings: Settings,
    clock: Clock,
    *,
    email: str,
    password: str,
    role: Role,
) -> User:
    email = email.lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise EmailTaken()
    now = clock.now()
    user = User(
        email=email, password_hash=security.hash_password(password), role=role, created_at=now
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        # Тот же адрес успел зарегистрироваться параллельным запросом.
        db.rollback()
        raise EmailTaken() from None
    mail = _verification_mail(db, settings, user, now)
    db.commit()
    mailer.send(mail)
    return user


def resend_verification(
    db: Session, mailer: Mailer, settings: Settings, clock: Clock, *, email: str
) -> None:
    """Для чужих и уже подтверждённых адресов молча ничего не делает — не раскрываем учётки."""
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None or user.email_verified:
        return
    mail = _verification_mail(db, settings, user, clock.now())
    db.commit()
    mailer.send(mail)


def verify_email(db: Session, clock: Clock, *, token: str) -> User:
    record = db.scalar(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == security.hash_email_token(token)
        )
    )
    if record is None:
        raise TokenInvalid()
    now = clock.now()
    if now >= record.expires_at:
        raise TokenExpired()
    user = db.get_one(User, record.user_id)
    user.email_verified_at = now
    db.execute(delete(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id))
    db.commit()
    return user


def authenticate(db: Session, *, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None or not security.verify_password(user.password_hash, password):
        raise InvalidCredentials()
    if not user.email_verified:
        raise EmailNotVerified()
    return user


def issue_session(user: User, settings: Settings, clock: Clock) -> str:
    """Токен входа со сроком `session_ttl_hours` от текущего момента."""
    ttl = timedelta(hours=settings.session_ttl_hours)
    return security.issue_access_token(user.id, settings.secret_key, ttl, clock.now())


def session_user(db: Session, secret: str, clock: Clock, *, token: str | None) -> User:
    """Пользователь по токену входа; подделанный, истёкший или чужой токен — не вход."""
    user_id = security.read_access_token(token, secret, clock.now()) if token else None
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise NotAuthenticated()
    return user


def _verification_mail(db: Session, settings: Settings, user: User, now: datetime) -> Mail:
    token, token_hash = security.new_email_token()
    ttl_hours = settings.email_token_ttl_hours
    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=token_hash,
            created_at=now,
            expires_at=now + timedelta(hours=ttl_hours),
        )
    )
    link = f"{settings.frontend_url}/verify-email?token={token}"
    return Mail(
        to=user.email,
        subject="Подтвердите адрес почты",
        text=(
            "Здравствуйте!\n\n"
            "Чтобы завершить регистрацию, откройте ссылку:\n"
            f"{link}\n\n"
            f"Ссылка действует {ttl_hours} ч. Если вы не регистрировались — "
            "просто удалите письмо.\n"
        ),
    )
