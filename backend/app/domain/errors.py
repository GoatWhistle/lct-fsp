"""Доменные ошибки: машинный `code` для фронта и человеческое `message` по-русски.

HTTP-статуса здесь нет — его назначает таблица в `app.controller.errors`; новой ошибке —
своя строка в таблице, `tests/test_errors.py` это проверяет.
"""

from datetime import datetime
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


class GradeNotNext(DomainError):
    code = "grade_not_next"
    message = "Попытка вверх — только на следующий грейд после вашего"


class GradeChangeTooEarly(DomainError):
    """Правило ожидания смены грейда (mechanics.md, §4): дата, с которой можно, — в
    `available_at`."""

    code = "grade_change_too_early"
    message = "Попытка на этот грейд пока недоступна — грейд меняется не чаще установленного срока"

    def __init__(self, available_at: datetime) -> None:
        super().__init__()
        self.available_at = available_at


class NoLowerGrade(DomainError):
    code = "no_lower_grade"
    message = "Ниже вашего грейда грейдов нет"


class AttemptInProgress(DomainError):
    """Одна незавершённая попытка на кандидата: тест на грейд и блок по теме не идут вместе."""

    code = "attempt_in_progress"
    message = "Сначала закончите начатый тест или блок по теме"


class TopicNotInCategory(DomainError):
    code = "topic_not_in_category"
    message = "Блок по теме — только по темам специализации вашей категории"


class TopicBlockTooEarly(DomainError):
    """Интервал блока по теме (mechanics.md, §6): дата, с которой можно, — в `available_at`."""

    code = "topic_block_too_early"
    message = "Блок по этой теме пока недоступен — по одной теме он проходится не чаще срока"

    def __init__(self, available_at: datetime) -> None:
        super().__init__()
        self.available_at = available_at


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


class ResumeTooLarge(DomainError):
    code = "resume_too_large"
    message = (
        "Резюме слишком большое — сохраните PDF покороче или без картинок, лимиты — под кнопкой "
        "загрузки"
    )


class ResumeUnreadable(DomainError):
    code = "resume_unreadable"
    message = "Не получилось прочитать файл как PDF — сохраните резюме в PDF заново"


class ResumeWithoutText(DomainError):
    code = "resume_without_text"
    message = (
        "В PDF нет текста, который можно прочитать: похоже на скан. Загрузите PDF, сохранённый "
        "из редактора, или заполните профиль вручную"
    )


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


class NotInSelection(DomainError):
    code = "not_in_selection"
    message = "Кандидата нет в выдаче подборки"


# Компания.


class CompanyRequired(DomainError):
    code = "company_required"
    message = "Сначала заполните профиль компании"


# Регулярные задания.


class TaskNotFound(DomainError):
    code = "task_not_found"
    message = "Задание не найдено — возможно, его сняли"


class TaskTopicsCount(DomainError):
    code = "task_topics_count"
    message = "Отметьте от одной до трёх тем"


class TaskTopicNotInSpecialization(DomainError):
    code = "task_topic_not_in_specialization"
    message = "Темы задания — только из тем его специализации"


class ReferenceAnswerMismatch(DomainError):
    code = "reference_answer_mismatch"
    message = "Эталон нужен заданию с эталоном и не нужен открытому"


class TaskLocked(DomainError):
    code = "task_locked"
    message = "На задание уже ответили или его сняли — править его нельзя"


class CategoryRequired(DomainError):
    code = "category_required"
    message = "Задания открываются после теста — сначала получите категорию"


class TaskAlreadyAnswered(DomainError):
    code = "task_already_answered"
    message = "Вы уже ответили на это задание"


class TaskAnswerNotFound(DomainError):
    code = "task_answer_not_found"
    message = "Ответ не найден"


class TaskNotGradable(DomainError):
    code = "task_not_gradable"
    message = "Ответ на задание с эталоном проверяет система"


class AnswerAlreadyGraded(DomainError):
    code = "answer_already_graded"
    message = "Ответ уже оценён"


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


class InvitationNotAccepted(DomainError):
    code = "invitation_not_accepted"
    message = "Переписка и отзыв доступа — только в принятом приглашении"


# Переписка.


class InvalidMessageText(DomainError):
    code = "invalid_message_text"
    message = "Сообщение пустое или слишком длинное"
