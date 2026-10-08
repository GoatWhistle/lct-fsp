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


# ФСП ID и достижения ФСП.


class FspIdUnavailable(DomainError):
    code = "fsp_id_unavailable"
    message = "ФСП ID сейчас недоступен — попробуйте позже или войдите по email"


class FspIdRejected(DomainError):
    code = "fsp_id_rejected"
    message = "Вход через ФСП ID не завершён — попробуйте ещё раз"


class FspAuthorizationInvalid(DomainError):
    code = "fsp_authorization_invalid"
    message = "Сеанс входа через ФСП ID устарел — начните заново"


class FspEmailUnverified(DomainError):
    code = "fsp_email_unverified"
    message = "В ФСП ID нет подтверждённого email — подтвердите его в ФСП ID или войдите по email"


class FspEmailTaken(DomainError):
    code = "fsp_email_taken"
    message = (
        "Учётка с этим email уже есть — войдите по email и привяжите ФСП ID в профиле кандидата"
    )


class FspIdTaken(DomainError):
    code = "fsp_id_taken"
    message = "Этот ФСП ID уже привязан к другой учётке"


class FspAlreadyLinked(DomainError):
    code = "fsp_already_linked"
    message = "К учётке уже привязан другой ФСП ID — сначала отвяжите его"


class FspNotLinked(DomainError):
    code = "fsp_not_linked"
    message = "ФСП ID не привязан"


class FspUnlinkForbidden(DomainError):
    code = "fsp_unlink_forbidden"
    message = "Учётка создана через ФСП ID и входит только через него — отвязать ID нельзя"


class FspRegistryUnavailable(DomainError):
    code = "fsp_registry_unavailable"
    message = "Реестр ФСП сейчас недоступен — показаны последние полученные достижения"


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
