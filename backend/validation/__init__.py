"""Стенд валидации: синтетические кандидаты с известной истиной проходят те же сценарии, что
HTTP, на in-memory хранилищах (docs/validation-plan.md).

Сборка стенда — `validation.main`, банк и поток кандидатов специализации — `validation.market`,
скрытая истина, модель ответа и эталонная релевантность — `validation.truth`, наборы D1 и D2
файлами — `validation.population`, прогон наборов для отчёта — `validation.simulate`, метрики
и отчёт — `validation.report`, команды — `validation.commands`. Запуск —
`uv run python -m validation [report | honesty | tune | parsing | market]` из `backend/`. Прод
(`main`, `composition`, `app`) пакет стенда не импортирует.
"""
