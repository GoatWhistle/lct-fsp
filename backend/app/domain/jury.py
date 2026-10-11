"""Режим жюри: демо-работодатель, компания, потребности и тестовый кандидат (mechanics.md, §18).

Данные синтетические и помечены: учётки режима жюри — `demo`, реальным работодателям они не
показываются. Работодатель один на стенд, кандидат — свежий на каждый вход.
"""

from app.domain.company import CompanyForm
from app.domain.importance import TopicImportance
from app.domain.need import NeedForm
from app.domain.work import WorkFormat

# Демо-засев (`seed_demo.py`) заводит учётки с известным паролем на этом домене. `.example`
# зарезервирован RFC 2606: реальный адрес на нём не подтвердить, значит, учётки — только засев.
SEED_DOMAIN = "demo.example"
DEMO_DOMAIN = "jury.example"
DEMO_EMPLOYER_EMAIL = f"employer@{DEMO_DOMAIN}"

DEMO_COMPANY = CompanyForm(
    name="Жюри-Технологии",
    industry="fintech",
    description="Платёжные сервисы для малого бизнеса. Компания синтетическая, режим жюри.",
    website=None,
    contact_email=f"hr@{DEMO_DOMAIN}",
    contact_phone=None,
)

_NO_EDITS: dict[str, TopicImportance] = {}

DEMO_NEEDS = (
    NeedForm(
        title="Middle бэкенд-разработчик",
        team_description="Команда платёжного ядра",
        specialization="backend",
        grade="middle",
        stack=("python", "fastapi", "postgresql"),
        topic_importance=_NO_EDITS,
        work_format=WorkFormat.hybrid,
        city="Москва",
        salary_from=250_000,
        salary_to=350_000,
    ),
    NeedForm(
        title="Middle фронтенд-разработчик",
        team_description="Команда личного кабинета",
        specialization="frontend",
        grade="middle",
        stack=("typescript", "react"),
        topic_importance=_NO_EDITS,
        work_format=WorkFormat.remote,
        city=None,
        salary_from=230_000,
        salary_to=320_000,
    ),
    NeedForm(
        title="Junior QA-инженер",
        team_description="Команда качества",
        specialization="qa",
        grade="junior",
        stack=("pytest", "postman"),
        topic_importance=_NO_EDITS,
        work_format=WorkFormat.office,
        city="Санкт-Петербург",
        salary_from=90_000,
        salary_to=130_000,
    ),
)
