"""Демо-засев: одна команда из `backend/` наполняет базу стенда демо-данными через прод-сценарии —
те же, что вызывает HTTP. Прямых INSERT нет.

    uv run python seed_demo.py                       # локально, база из .env
    docker compose exec backend python seed_demo.py  # в compose

Засевается:

- кандидаты каждой категории «специализация × грейд»: без ФСП и с ФСП, прошедшие тест, с
  заполненной анкетой. Кандидат с ФСП привязан к демо-участнику ФСП ID той же категории
  (`fsp_stub.DEMO_PERSONAS`), поэтому `sub` в Keycloak и в реестре совпадают;
- работодатели с компаниями и потребностями.

Все учётки — с подтверждённым адресом и паролем `DEMO_PASSWORD`, список — README, «Демо-данные».
Повторный запуск ничего не дублирует и продолжает прерванный: каждый шаг сперва смотрит, сделан
ли он.

Сборка — `main.create_app`, та же проводка, что у прода. Заменены только порты, которым в засеве
нечего делать снаружи: почта — в память (ссылку подтверждения засев читает сам), ФСП ID — в
память (код за демо-участника выдаёт засев), часы — симулятор (время ответа задаёт модель
ответа), seed механики — производный от `DEMO_SEED`. Отвечает на задания модель ответа стенда
валидации по истине из генератора синтетического рынка: засев — не прод, стенд ему можно.
"""

import argparse
import logging
import random
import re
import uuid
from contextlib import closing, suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import fsp_stub
from app.adapter.clock import SimulatedClock
from app.adapter.fsp_id import MemoryFspId
from app.adapter.mail import MemoryMailer
from app.adapter.seed import DerivedSeeds
from app.domain.account import Account, Role
from app.domain.attempt import PathView, Stage
from app.domain.candidate import ProfileForm
from app.domain.company import CompanyForm, CompanySize
from app.domain.errors import EmailNotVerified, EmailTaken
from app.domain.fsp import FspIdentity, FspIntent
from app.usecase import candidate as candidate_usecase
from app.usecase.account import Accounts
from app.usecase.attempt import CandidatePath
from app.usecase.interface import PasswordHasher
from composition import experience_limits
from main import create_app
from settings import Mechanics, Settings
from validation.main import catalog
from validation.market import WRONG
from validation.population import D1, EXPERIENCE_YEARS, ROLE, Generator, SalaryPosition
from validation.truth import CandidateTruth, Persona, guessing, respond

DEMO_SEED = 20261008
DEMO_PASSWORD = "demo-2026"
DOMAIN = "demo.example"
# Истинный уровень демо-кандидата — над порогом грейда на столько, но в полосе грейда (полосы —
# по 1,0): истинный грейд, зарплата и стаж — той же категории. Темы — с малым разбросом, заявка —
# сам грейд. Тест обычно даёт ровно эту категорию; если нет, засев берёт следующего кандидата
# той же категории, но не больше `MAX_TRIES`.
LEVEL_MARGIN = 0.8
TOPIC_SD = 0.2
MAX_TRIES = 5
# Часы засева начинаются за столько до запуска: время ответов — по модели, а не по часам машины.
START_AGO = timedelta(days=14)

NAMES = (
    "Алексей Смирнов",
    "Анна Кузнецова",
    "Борис Попов",
    "Вера Соколова",
    "Глеб Лебедев",
    "Дарья Козлова",
    "Егор Новиков",
    "Елена Морозова",
    "Иван Петров",
    "Ксения Волкова",
    "Максим Соловьёв",
    "Наталья Васильева",
    "Олег Зайцев",
    "Полина Павлова",
    "Роман Семёнов",
    "Светлана Голубева",
    "Тимур Виноградов",
    "Ульяна Богданова",
    "Фёдор Воробьёв",
    "Юлия Фёдорова",
)
SOFT_SKILLS = ("командная работа", "ответственность", "обучаемость", "коммуникабельность")


@dataclass(frozen=True)
class DemoEmployer:
    email: str
    company: CompanyForm
    position: SalaryPosition
    # Потребности: специализация и грейд.
    needs: tuple[tuple[str, str], ...]
    fsp_partner: bool = False


EMPLOYERS = (
    DemoEmployer(
        f"employer@{DOMAIN}",
        CompanyForm(
            name="Демо-Технологии",
            industry="fintech",
            description="Платёжные сервисы для малого бизнеса. Компания синтетическая.",
            # Сайт — для метки доверия: адрес hr@tech.demo.example подтверждается письмом в Mailpit.
            website=f"https://tech.{DOMAIN}",
            contact_email=f"hr@{DOMAIN}",
            contact_phone=None,
            size=CompanySize.up_to_200,
            it_accredited=True,
            benefits=("health", "education", "conferences", "equipment"),
            links=(
                "https://t.me/demo_tech",
                "https://habr.com/ru/companies/demo-tech",
                "https://github.com/demo-tech",
                "https://vk.com/demo_tech",
            ),
        ),
        SalaryPosition.market,
        (
            ("backend", "middle"),
            ("frontend", "middle"),
            ("data-ml", "middle"),
            ("qa", "junior"),
            ("devops", "senior"),
        ),
        fsp_partner=True,
    ),
    DemoEmployer(
        f"employer-2@{DOMAIN}",
        CompanyForm(
            name="Демо-Ритейл",
            industry="e-commerce",
            description="Маркетплейс товаров для дома. Компания синтетическая.",
            website=f"https://retail.{DOMAIN}",
            contact_email=f"jobs@{DOMAIN}",
            contact_phone=None,
            size=CompanySize.over_1000,
            benefits=("health", "sport", "meals", "relocation"),
            links=("https://t.me/demo_retail", "https://vk.com/demo_retail"),
        ),
        SalaryPosition.below,
        (
            ("backend", "junior"),
            ("backend", "senior"),
            ("frontend", "intern"),
            ("qa", "middle"),
            ("data-ml", "senior"),
        ),
    ),
)


def candidate_email(specialization: str, grade: str, *, fsp: bool, attempt: int = 1) -> str:
    """`backend-middle@…`, с ФСП — `backend-middle-fsp@…`; запасной кандидат — с номером."""
    suffix = "-fsp" if fsp else ""
    again = f"-{attempt}" if attempt > 1 else ""
    return f"{specialization}-{grade}{suffix}{again}@{DOMAIN}"


@dataclass(frozen=True)
class Seeded:
    # Кандидат с категорией: email, специализация, грейд, логин ФСП ID или None.
    candidates: tuple[tuple[str, str, str, str | None], ...]
    employers: tuple[str, ...]
    needs: int


class Seeder:
    def __init__(
        self,
        settings: Settings,
        mechanics: Mechanics,
        *,
        passwords: PasswordHasher | None = None,
        now: datetime | None = None,
    ) -> None:
        self.mechanics = mechanics
        self.clock = SimulatedClock((now or datetime.now(UTC)) - START_AGO)
        self.mailer = MemoryMailer()
        self.fsp_id = MemoryFspId()
        self.app = create_app(
            settings,
            mechanics,
            mailer=self.mailer,
            clock=self.clock,
            seeds=DerivedSeeds(DEMO_SEED),
            passwords=passwords,
            fsp_id=self.fsp_id,
        )
        self.state = self.app.state
        known = catalog()
        self.generator = Generator(D1, mechanics, known)
        self.specializations = list(known.specializations)
        self.grades = self.generator.grades
        # Истинные параметры семейств — как у набора D1.
        self.families = self.generator.families()
        realm, _ = fsp_stub.generate()
        self.fsp_users = {u["username"]: u for u in realm["users"]}

    def run(self) -> Seeded:
        candidates = []
        for code in self.specializations:
            for grade in self.grades:
                for fsp in (False, True):
                    found = self.category_candidate(code, grade, fsp=fsp)
                    if found is not None:
                        candidates.append(found)
        needs = sum(self.employer(e) for e in EMPLOYERS)
        return Seeded(tuple(candidates), tuple(e.email for e in EMPLOYERS), needs)

    def category_candidate(
        self, code: str, grade: str, *, fsp: bool
    ) -> tuple[str, str, str, str | None] | None:
        """Кандидат категории `code × grade`: следующий пробуется, пока тест не даст её."""
        login = fsp_stub.demo_username(code, grade) if fsp else None
        for attempt in range(1, MAX_TRIES + 1):
            email = candidate_email(code, grade, fsp=fsp, attempt=attempt)
            # Свой поток на истину, ответы и анкету: продолженный засев, где ответов уже нет,
            # пишет ту же анкету.
            truth = self.generator.truth(
                code,
                Persona.honest,
                random.Random(f"{DEMO_SEED}:{email}:truth"),
                common=self.mechanics.grade_thresholds[grade] + LEVEL_MARGIN,
                topic_sd=TOPIC_SD,
                claimed=grade,
            )
            account = self.account(email, Role.candidate)
            view = self.take_test(account.id, truth, random.Random(f"{DEMO_SEED}:{email}:test"))
            self.profile(account.id, email, truth, random.Random(f"{DEMO_SEED}:{email}:profile"))
            category = view.category
            if category and (category.specialization.code, category.grade.code) == (code, grade):
                if login is not None:
                    self.link_fsp(account, login)
                return email, code, grade, login
        return None

    def account(self, email: str, role: Role) -> Account:
        """Учётка с подтверждённым адресом; есть — та же. Прерванный засев мог оставить её
        неподтверждённой — тогда новая ссылка."""
        with closing(self.state.unit_of_work()) as uow:
            accounts: Accounts = self.state.accounts(uow)
            with suppress(EmailTaken):
                accounts.register(email, DEMO_PASSWORD, role)
            try:
                return accounts.sign_in(email, DEMO_PASSWORD).account
            except EmailNotVerified:
                accounts.resend_verification(email)
            accounts.verify_email(self.verification_token(email))
            return accounts.sign_in(email, DEMO_PASSWORD).account

    def verification_token(self, email: str) -> str:
        mail = next(m for m in reversed(self.mailer.sent) if m.to == email)
        found = re.search(r"/verify-email\?token=(\S+)", mail.text)
        assert found, "в письме нет ссылки подтверждения"
        return found.group(1)

    def take_test(self, user: uuid.UUID, truth: CandidateTruth, rng: random.Random) -> PathView:
        """Путь кандидата до категории или до «без категории» — с того шага, где он стоит."""
        model = self.generator.params.response
        with closing(self.state.unit_of_work()) as uow:
            paths: CandidatePath = self.state.candidate_path(uow)
            calibrations = self.state.answer_calibration(uow)
            view = paths.path(user)
            while True:
                match view.stage:
                    case Stage.survey:
                        view = paths.submit_survey(user, specialization=truth.specialization)
                    case Stage.grade:
                        view = paths.start_attempt(user, grade=truth.claimed)
                    case Stage.offer:
                        assert view.offer_grade is not None
                        view = paths.start_attempt(user, grade=view.offer_grade)
                    case Stage.test:
                        item = paths.current_item(user)
                        response = respond(
                            truth,
                            item.family_code,
                            item.topic.code,
                            self.families[item.family_code],
                            guessing(item.instance, model),
                            model,
                            rng,
                        )
                        self.clock.advance(timedelta(seconds=response.seconds))
                        answered = paths.answer(
                            user,
                            presentation_id=item.presentation_id,
                            response=item.instance.answer if response.correct else WRONG,
                        )
                        calibrations.calibrate(answered.answer)
                        view = answered.view
                    case _:
                        return view

    def profile(
        self, user: uuid.UUID, email: str, truth: CandidateTruth, rng: random.Random
    ) -> None:
        """Анкета — один раз: повторный запуск начинает часы раньше прошлого и не должен
        переписывать её задним числом."""
        with closing(self.state.unit_of_work()) as uow:
            own = candidate_usecase.own_profile(
                uow,
                self.state.candidate_repository(uow),
                user,
                self.clock,
                self.state.profile_freshness,
            )
        if own.profile is not None:
            return
        stack, about = self.generator.self_description(truth, (), rng)
        low, high = EXPERIENCE_YEARS[truth.grade]
        form = ProfileForm(
            full_name=rng.choice(NAMES),
            contact_email=email,
            contact_phone=None,
            telegram=None,
            about=about,
            job_roles=(ROLE[truth.specialization],),
            soft_skills=tuple(rng.sample(SOFT_SKILLS, 2)),
            stack=stack,
            experience_years=rng.randint(low, high),
            work_formats=truth.work_formats,
            city=truth.city,
            relocation=truth.relocation,
            industries=(),
            expected_salary=truth.expected_salary,
        )
        with closing(self.state.unit_of_work()) as uow:
            candidate_usecase.save_profile(
                uow,
                self.state.candidate_repository(uow),
                user,
                form,
                self.clock,
                self.state.profile_freshness,
                experience_limits=experience_limits(self.mechanics),
            )

    def link_fsp(self, account: Account, login: str) -> None:
        """Привязка демо-участника ФСП ID — тем же сценарием, что кнопка «Привязать ФСП ID»."""
        user = self.fsp_users[login]
        with closing(self.state.unit_of_work()) as uow:
            fsp = self.state.fsp_accounts(uow)
            if fsp.status(account).fsp_id == user["id"]:
                return
            started = fsp.start(FspIntent.link, account)
            state = started.authorization.state
            identity = FspIdentity(user["id"], user["email"], user["emailVerified"])
            code = self.fsp_id.issue(identity, state)
            fsp.complete(started.authorization, state=state, code=code, user=account)

    def employer(self, demo: DemoEmployer) -> int:
        """Работодатель, компания и недостающие потребности; возвращает число потребностей."""
        account = self.account(demo.email, Role.employer)
        with closing(self.state.unit_of_work()) as uow:
            companies = self.state.companies(uow)
            companies.save(account.id, demo.company)
            companies.mark_fsp_partner(account.id, demo.fsp_partner)
            needs = self.state.needs(uow)
            titles = {view.record.need.title for view in needs.all(account.id)}
            for code, grade in demo.needs:
                rng = random.Random(f"{DEMO_SEED}:{demo.email}:{code}:{grade}")
                form = self.generator.need_form(code, grade, demo.company.name, demo.position, rng)
                if form.title not in titles:
                    needs.create(account.id, form)
            return len(needs.all(account.id))


def seed(
    settings: Settings | None = None,
    *,
    passwords: PasswordHasher | None = None,
    now: datetime | None = None,
) -> Seeded:
    settings = settings or Settings()
    mechanics = Mechanics.from_yaml(settings.mechanics_file)
    seeder = Seeder(settings, mechanics, passwords=passwords, now=now)
    try:
        return seeder.run()
    finally:
        seeder.app.state.engine.dispose()


def main() -> None:
    argparse.ArgumentParser(prog="python seed_demo.py", description=__doc__).parse_args()
    # Первые попытки идут по пустому окну показов: предупреждения о потолке показов ожидаемы
    # и забили бы вывод.
    logging.basicConfig(level=logging.ERROR)
    found = seed()
    print(
        f"Засеяно: кандидатов с категорией {len(found.candidates)}, работодателей "
        f"{len(found.employers)}, потребностей {found.needs}. Пароль всех учёток — {DEMO_PASSWORD}"
    )
    for email, code, grade, login in found.candidates:
        print(f"  {email}: {code} × {grade}" + (f", ФСП ID {login}" if login else ""))


if __name__ == "__main__":
    main()
