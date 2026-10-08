"""Доменные ошибки: машинный `code` для фронта и человеческое `message` по-русски.

HTTP-статуса здесь нет — его назначает таблица в `app.controller.errors`; новой ошибке —
своя строка в таблице, `tests/test_errors.py` это проверяет.
"""

from typing import ClassVar


class DomainError(Exception):
    code: ClassVar[str] = "bad_request"
    message: ClassVar[str] = "Некорректный запрос"

    def __init__(self) -> None:
        super().__init__(self.message)


# Вход и роли.


class NotAuthenticated(DomainError):
    code = "not_authenticated"
    message = "Войдите, чтобы продолжить"


class WrongRole(DomainError):
    code = "wrong_role"
    message = "Раздел доступен другой роли"


class EmailTaken(DomainError):
    code = "email_taken"
    message = "Этот email уже зарегистрирован — войдите"


class TokenInvalid(DomainError):
    code = "token_invalid"
    message = "Ссылка недействительна. Если адрес уже подтверждён — просто войдите"


class TokenExpired(DomainError):
    code = "token_expired"
    message = "Срок ссылки истёк — запросите новое письмо"


class InvalidCredentials(DomainError):
    code = "invalid_credentials"
    message = "Неверный email или пароль"


class EmailNotVerified(DomainError):
    code = "email_not_verified"
    message = "Адрес не подтверждён. Откройте ссылку из письма или запросите новое"


# Справочники.


class SpecializationNotFound(DomainError):
    code = "specialization_not_found"
    message = "Такой специализации нет в справочнике"


class UnknownIndustry(DomainError):
    code = "unknown_industry"
    message = "Такой сферы бизнеса нет в справочнике"


class UnknownSpecialization(DomainError):
    code = "unknown_specialization"
    message = "Такой специализации нет в справочнике"


class UnknownGrade(DomainError):
    code = "unknown_grade"
    message = "Такого грейда нет в справочнике"


class UnknownTechnology(DomainError):
    code = "unknown_technology"
    message = "Такой технологии нет в справочнике"


# Путь кандидата и тест.


class SpecializationWithoutTest(DomainError):
    code = "specialization_without_test"
    message = "Тест по этой специализации ещё готовится — выберите другую"


class StepUnavailable(DomainError):
    code = "path_step_unavailable"
    message = "Этот шаг сейчас недоступен — обновите страницу"


class GradeNotOffered(DomainError):
    code = "grade_not_offered"
    message = "Продолжить можно только на предложенном грейде"


class NoTestInProgress(DomainError):
    code = "no_test_in_progress"
    message = "Сейчас нет начатого теста"


class ItemNotCurrent(DomainError):
    code = "item_not_current"
    message = "Это задание уже не текущее — обновите страницу"


# Профиль кандидата.


class ProfileNotFound(DomainError):
    code = "profile_not_found"
    message = "Сначала заполните профиль"


class CandidateNotFound(DomainError):
    code = "candidate_not_found"
    message = "Кандидат не найден"


class CityRequired(DomainError):
    code = "city_required"
    message = "Укажите город — для офиса и гибрида он обязателен"


# Потребность и подборка.


class NeedNotFound(DomainError):
    code = "need_not_found"
    message = "Потребность не найдена — возможно, её удалили"


class TopicNotInSpecialization(DomainError):
    code = "topic_not_in_specialization"
    message = "Важность задаётся только темам специализации потребности"


class InvalidSalaryRange(DomainError):
    code = "invalid_salary_range"
    message = "Вилка — обе границы больше нуля, «от» не больше «до»"


class SelectionNotFound(DomainError):
    code = "selection_not_found"
    message = "Подборка не найдена"


# Приглашения.


class InvitationNotFound(DomainError):
    code = "invitation_not_found"
    message = "Приглашение не найдено"


class CompanyProfileRequired(DomainError):
    code = "company_profile_required"
    message = "Сначала заполните профиль компании — кандидат увидит его в приглашении"


class InvitationTransitionNotAllowed(DomainError):
    code = "invitation_transition_not_allowed"
    message = "На это приглашение уже ответили — обновите страницу"


class InvitationExpired(InvitationTransitionNotAllowed):
    code = "invitation_expired"
    message = "Срок ответа на приглашение истёк"


class InvitationAlreadyOpen(DomainError):
    code = "invitation_already_open"
    message = "Кандидат ещё не ответил на прошлое приглашение компании — дождитесь ответа"


class InvitationBudgetExhausted(DomainError):
    code = "invitation_budget_exhausted"
    message = "Бюджет приглашений на эту неделю исчерпан — он обновится в понедельник"
