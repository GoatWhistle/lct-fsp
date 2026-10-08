"""Стенд валидации: синтетические кандидаты с известной истиной проходят те же сценарии, что
HTTP, на in-memory хранилищах (docs/validation-plan.md).

Сборка стенда — `validation.main`, синтетический рынок — `validation.market`, команды —
`validation.commands`. Запуск — `uv run python -m validation [honesty | tune]` из `backend/`.
Прод (`main`, `composition`, `app`) пакет стенда не импортирует.
"""
