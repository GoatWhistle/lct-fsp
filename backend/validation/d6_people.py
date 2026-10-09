"""D6: вымышленные люди набора — истина резюме (docs/validation-plan.md, D6; формат —
validation/data/resume_pdfs.md).

Люди придуманы вручную и не взяты ни из разбора, ни из настоящих резюме: имена, почты на
`example.*` и телефоны из диапазона 555-01 никому не принадлежат. Названия технологий в тексте
резюме — названия справочника, должности — слова словаря ролей: разбор по этой истине не
подбирался и под неё не настраивается (ADR 0002).
"""

from dataclasses import dataclass
from datetime import date

# «Сейчас» набора: по нему считается стаж записей «по настоящее время».
AS_OF = date(2026, 10, 8)


@dataclass(frozen=True)
class Job:
    start: str
    end: str | None
    title: str
    role: str
    company: str
    stack: tuple[str, ...]
    summary: str


@dataclass(frozen=True)
class Person:
    slug: str
    specialization: str
    layout: str
    full_name: str
    email: str
    phone: str
    telegram: str
    jobs: tuple[Job, ...]
    skills: tuple[str, ...]
    education: str

    @property
    def stack(self) -> tuple[str, ...]:
        seen = dict.fromkeys((*self.skills, *(code for job in self.jobs for code in job.stack)))
        return tuple(seen)

    @property
    def roles(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(job.role for job in self.jobs))

    @property
    def experience_months(self) -> int:
        return union_months([(job.start, job.end) for job in self.jobs])

    @property
    def experience_years(self) -> int:
        return self.experience_months // 12


def month_index(value: str) -> int:
    year, month = value.split("-")
    return int(year) * 12 + int(month)


def union_months(periods: list[tuple[str, str | None]]) -> int:
    """Месяцы в объединении периодов; оба конца включены, `None` — месяц `AS_OF`."""
    now = AS_OF.year * 12 + AS_OF.month
    spans = sorted((month_index(s), now if e is None else month_index(e)) for s, e in periods)
    total, reach = 0, 0
    for begin, end in spans:
        begin = max(begin, reach + 1)
        if end >= begin:
            total += end - begin + 1
            reach = end
    return total


PEOPLE = (
    Person(
        "andreev",
        "backend",
        "one_column",
        "Андреев Кирилл Олегович",
        "kirill.andreev@example.ru",
        "+7 900 555-01-01",
        "kirill_andreev_dev",
        (
            Job(
                "2023-09",
                None,
                "Бэкенд-разработчик",
                "Бэкенд-разработчик",
                "ООО «Верфь»",
                ("python", "fastapi", "postgresql", "redis"),
                "Сервис заказов: проектирование API, миграции, кэширование горячих данных.",
            ),
            Job(
                "2022-06",
                "2023-08",
                "Стажёр-разработчик",
                "Стажёр",
                "АО «Нева-софт»",
                ("python", "pytest"),
                "Исправлял ошибки в обработке платежей, писал тесты на проверку расчётов.",
            ),
        ),
        ("python", "fastapi", "postgresql", "redis", "docker", "pytest"),
        "2018 — 2022, СПбГУ, математика и компьютерные науки",
    ),
    Person(
        "belova",
        "frontend",
        "two_columns",
        "Белова Дарья Игоревна",
        "daria.belova@example.org",
        "+7 900 555-01-02",
        "daria_belova_ui",
        (
            Job(
                "2022-03",
                None,
                "Фронтенд-разработчик",
                "Фронтенд-разработчик",
                "ООО «Кварц»",
                ("react", "typescript", "jest"),
                "Личный кабинет клиента: формы, таблицы, тесты интерфейса.",
            ),
            Job(
                "2020-09",
                "2022-02",
                "Верстальщик",
                "Фронтенд-разработчик",
                "Студия «Пиксель»",
                ("html-css", "javascript"),
                "Адаптивная вёрстка лендингов и почтовых рассылок.",
            ),
        ),
        ("javascript", "typescript", "react", "html-css", "jest", "vite"),
        "2016 — 2020, НИУ ВШЭ, дизайн и программирование",
    ),
    Person(
        "volkov",
        "data-ml",
        "table",
        "Волков Артём Сергеевич",
        "artem.volkov@example.com",
        "+7 900 555-01-03",
        "artem_volkov_ds",
        (
            Job(
                "2021-05",
                None,
                "Data Scientist",
                "Data Scientist",
                "ПАО «Стрела»",
                ("python", "scikit-learn", "catboost", "airflow"),
                "Модели оттока клиентов, расчёт и выкладка еженедельных скоров.",
            ),
            Job(
                "2019-08",
                "2021-04",
                "Аналитик данных",
                "Аналитик данных",
                "ООО «Лагуна»",
                ("pandas", "postgresql"),
                "Отчёты по продажам, выгрузки, проверка гипотез на A/B-тестах.",
            ),
        ),
        ("python", "pandas", "numpy", "scikit-learn", "catboost", "postgresql", "airflow"),
        "2014 — 2019, МГУ, механико-математический факультет",
    ),
    Person(
        "gromova",
        "qa",
        "builder",
        "Громова Алина Павловна",
        "alina.gromova@example.net",
        "+7 900 555-01-04",
        "alina_gromova_qa",
        (
            Job(
                "2024-01",
                None,
                "QA-инженер",
                "QA-инженер",
                "ООО «Лотос»",
                ("python", "pytest", "postman", "selenium"),
                "Автотесты веб-интерфейса и API, регрессионные прогоны перед релизом.",
            ),
        ),
        ("python", "pytest", "postman", "selenium", "postgresql"),
        "2019 — 2023, РУДН, информационные системы",
    ),
    Person(
        "denisov",
        "devops",
        "jobsite",
        "Денисов Максим Андреевич",
        "maxim.denisov@example.ru",
        "+7 900 555-01-05",
        "maxim_denisov_ops",
        (
            Job(
                "2020-04",
                None,
                "DevOps-инженер",
                "DevOps-инженер",
                "ООО «Фарватер»",
                ("kubernetes", "terraform", "gitlab-ci", "prometheus", "grafana"),
                "Кластеры и окружения как код, конвейеры доставки, дежурства по инцидентам.",
            ),
            Job(
                "2017-09",
                "2020-03",
                "Системный администратор",
                "Системный администратор",
                "ООО «Меридиан»",
                ("linux", "bash", "ansible"),
                "Сопровождал серверы и сеть офиса, автоматизировал настройку рабочих мест.",
            ),
        ),
        ("linux", "bash", "docker", "kubernetes", "terraform", "ansible", "gitlab-ci"),
        "2012 — 2017, МИФИ, информационная безопасность",
    ),
    Person(
        "egorova",
        "backend",
        "latex",
        "Егорова Полина Викторовна",
        "polina.egorova@example.org",
        "+7 900 555-01-06",
        "polina_egorova_be",
        (
            Job(
                "2023-06",
                None,
                "Тимлид бэкенда",
                "Тимлид",
                "АО «Горизонт»",
                ("java", "spring", "kafka"),
                "Команда из шести человек, планирование релизов, ревью архитектуры.",
            ),
            Job(
                "2019-03",
                "2023-05",
                "Java-разработчик",
                "Бэкенд-разработчик",
                "АО «Горизонт»",
                ("java", "spring", "postgresql", "docker"),
                "Платёжный шлюз: интеграции с банками, очереди, мониторинг задержек.",
            ),
        ),
        ("java", "spring", "postgresql", "kafka", "docker"),
        "2013 — 2018, ИТМО, программная инженерия",
    ),
    Person(
        "zhukov",
        "frontend",
        "multipage",
        "Жуков Игорь Николаевич",
        "igor.zhukov@example.net",
        "+7 900 555-01-07",
        "igor_zhukov_fe",
        (
            Job(
                "2022-01",
                None,
                "Фронтенд-разработчик",
                "Фронтенд-разработчик",
                "ООО «Атлас»",
                ("vue", "typescript", "playwright"),
                "Редактор отчётов на Vue, сквозные тесты основных сценариев.",
            ),
            Job(
                "2018-07",
                "2021-12",
                "Fullstack-разработчик",
                "Fullstack-разработчик",
                "ООО «Север»",
                ("javascript", "nodejs", "postgresql", "html-css"),
                "Складской портал: клиентская часть, серверные обработчики и отчёты.",
            ),
        ),
        ("javascript", "typescript", "vue", "nodejs", "html-css", "postgresql", "playwright"),
        "2013 — 2018, Томский политехнический университет, прикладная информатика",
    ),
    Person(
        "zaitseva",
        "data-ml",
        "one_column",
        "Зайцева Мария Антоновна",
        "maria.zaitseva@example.com",
        "+7 900 555-01-08",
        "maria_zaitseva_ml",
        (
            Job(
                "2023-02",
                None,
                "ML-инженер",
                "ML-инженер",
                "ООО «Юла-тех»",
                ("python", "pytorch", "mlflow", "docker"),
                "Обучение и выкладка моделей поиска, учёт экспериментов и версий моделей.",
            ),
            Job(
                "2021-10",
                "2023-01",
                "Инженер данных",
                "Инженер данных",
                "ООО «Юла-тех»",
                ("spark", "clickhouse", "airflow"),
                "Витрины данных, ежедневные расчёты, контроль качества загрузок.",
            ),
        ),
        ("python", "pytorch", "mlflow", "spark", "airflow", "clickhouse", "docker"),
        "2016 — 2021, Новосибирский государственный университет, математика",
    ),
    Person(
        "isaev",
        "qa",
        "jobsite",
        "Исаев Тимур Рустамович",
        "timur.isaev@example.org",
        "+7 900 555-01-09",
        "timur_isaev_aqa",
        (
            Job(
                "2025-03",
                None,
                "Автотестировщик",
                "QA-инженер",
                "ООО «Дельта»",
                ("java", "selenium", "jmeter"),
                "Автотесты личного кабинета, нагрузочные проверки перед сезонными пиками.",
            ),
            Job(
                "2024-06",
                "2025-02",
                "Стажёр",
                "Стажёр",
                "ООО «Дельта»",
                ("postman", "mysql"),
                "Ручное тестирование, проверка API, заведение и разбор дефектов.",
            ),
        ),
        ("java", "selenium", "jmeter", "postman", "mysql"),
        "2020 — 2024, КФУ, прикладная информатика",
    ),
    Person(
        "kalinina",
        "devops",
        "two_columns",
        "Калинина Вера Дмитриевна",
        "vera.kalinina@example.net",
        "+7 900 555-01-10",
        "vera_kalinina_sre",
        (
            Job(
                "2022-09",
                None,
                "DevOps-инженер",
                "DevOps-инженер",
                "ООО «Прибой»",
                ("docker", "github-actions", "ansible", "prometheus", "nginx"),
                "Конвейеры сборки, настройка серверов, оповещения о сбоях сервисов.",
            ),
        ),
        ("linux", "docker", "github-actions", "ansible", "prometheus", "nginx"),
        "2017 — 2021, УрФУ, информационные технологии",
    ),
)
