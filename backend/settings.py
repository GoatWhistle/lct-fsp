"""Конфигурация — инфраструктура сборки рядом с точками сборки `main.py` и `validation/main.py`.

`Settings` — где что лежит и как работает вход (БД, почта, секреты, адреса, сроки); читается из
переменных окружения и `.env`. `Mechanics` — числа механик теста, профиля, подбора и рынка из
`config/mechanics.yaml`; имена и значения — как в `docs/parameters.md`, тест сверяет. Вне слоёв
`app` (docs/adr/0001-layers-and-ports.md): `Settings` читают только точки сборки, `Mechanics` —
ещё сценарии и контроллер. В эндпоинт `Mechanics` приходит через `MechanicsDep`.
"""

from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent
MECHANICS_FILE = BACKEND_DIR / "config" / "mechanics.yaml"
# Справочники: грейды, сферы бизнеса, специализации с темами, технологии, дисциплины ФСП.
CATALOG_FILE = BACKEND_DIR / "config" / "catalog.yaml"
# Словарь синонимов для разбора потребности из текста на правилах.
SYNONYMS_FILE = BACKEND_DIR / "config" / "synonyms.yaml"
# Заглушка реестра ФСП — синтетика, её и realm Keycloak генерирует `fsp_stub.py`.
FSP_REGISTRY_FILE = BACKEND_DIR / "config" / "fsp_registry.json"
# Матрица грейдов и документ для жюри, который генерируется из неё.
GRADE_MATRIX_FILE = BACKEND_DIR / "config" / "grade_matrix.yaml"
GRADE_MATRIX_DOC = BACKEND_DIR.parent / "docs" / "grade-matrix.md"
# Модель принятия CatBoost — версионируется в репо.
ACCEPTANCE_MODEL_FILE = BACKEND_DIR / "app" / "adapter" / "acceptance_model.cbm"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://lct:lct@localhost:5432/lct"
    # Подпись входа; на стенде — своя случайная строка (`openssl rand -hex 32`).
    secret_key: str = Field(default="dev-only-secret-key-change-me-on-deploy", min_length=32)
    frontend_url: str = "http://localhost:3000"
    cookie_secure: bool = False

    smtp_host: str = "localhost"
    smtp_port: int = 1025
    mail_from: str = "Подбор ФСП <no-reply@lct.local>"

    email_token_ttl_hours: int = Field(default=24, gt=0, description="Срок ссылки подтверждения")
    session_ttl_hours: int = Field(default=168, gt=0, description="Срок входа")

    mechanics_file: Path = MECHANICS_FILE
    catalog_file: Path = CATALOG_FILE
    synonyms_file: Path = SYNONYMS_FILE

    # Разбор текста за портом `TextUnderstanding` (docs/adr/0002-text-understanding-port.md):
    # реализация по имени — `rules` или `llama` — и сколько ждать модель, прежде чем ответить
    # правилами. По умолчанию правила: модель становится вариантом по умолчанию только по замеру.
    text_understanding: str = "rules"
    text_understanding_timeout_seconds: float = Field(default=10.0, gt=0)
    # `llama-server` из llama.cpp — сервис compose под profile `llama`; модель GGUF выбирает
    # compose, имя здесь — для запроса.
    llama_url: str = "http://llama:8080"
    llama_model: str = "local"

    # ФСП ID — OpenID Connect. Настоящий ФСП ID — смена этих значений, без правки кода.
    # Публичный адрес realm: его видит браузер, он же `iss` в токенах.
    fsp_id_issuer: str = "http://localhost:8080/realms/fsp-id"
    # Адрес, по которому до ФСП ID ходит бэкенд, если он другой (в compose — имя сервиса).
    fsp_id_server_url: str | None = None
    fsp_id_client_id: str = "lct-platform"
    fsp_id_client_secret: str = "dev-only-fsp-id-client-secret"
    # Куда ФСП ID возвращает браузер; по умолчанию — callback бэкенда за адресом фронта.
    fsp_id_redirect_uri: str | None = None
    fsp_registry_path: Path = FSP_REGISTRY_FILE
    # Модель принятия, обученная стендом (`python -m validation acceptance`); файла нет —
    # множитель 1, подборка по одному соответствию.
    acceptance_model_file: Path = ACCEPTANCE_MODEL_FILE

    @property
    def fsp_id_callback(self) -> str:
        return self.fsp_id_redirect_uri or f"{self.frontend_url}/api/auth/fsp/callback"


class Mechanics(BaseModel):
    """Параметры механик; смысл, единицы и обоснование — в docs/parameters.md."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    # Шкала и категория
    grade_thresholds: dict[str, float]
    grade_confidence: float
    grade_up_hint_confidence: float
    theta_prior_sd: float
    topic_deviation_sd: float
    level_sd_inflation: float
    grade_change_interval_days: int
    grade_retry_interval_days: int
    no_category_retest_days: int
    confidence_language_bands: list[float]

    # Банк заданий
    expert_difficulty_by_grade: dict[str, float]
    expert_discrimination: float
    bank_min_families_per_topic: int
    bank_min_families_per_grade: int
    bank_max_trace_share_per_topic: float = Field(ge=0, le=1)
    bank_min_scenario_families_per_grade: int = Field(ge=0)
    anchor_families_per_topic: int
    family_answer_collision_max: float
    family_instance_difficulty_sd_max: float

    # Адаптивный тест
    test_min_items: int
    test_max_items: int
    test_stop_sd: float
    test_min_items_per_topic: int
    test_max_topic_share: float
    exposure_top_k: int
    exposure_max_rate: float
    exposure_window_attempts: int
    topic_block_items: int
    topic_block_interval_days: int

    # Калибровка
    elo_k_initial: float
    elo_k_half_responses: int
    elo_k_min: float
    calibration_refit_min_responses: int
    calibration_expert_gap_review: float
    calibration_refit_difficulty_prior_sd: float
    calibration_refit_log_discrimination_prior_sd: float
    calibration_link_window_attempts: int
    item_fit_groups: int = Field(gt=0)
    item_fit_rmsd_max: float = Field(ge=0)
    item_fit_discrimination_min: float = Field(ge=0)
    item_fit_ceiling_gain_max: float = Field(ge=0)
    item_fit_ceiling_min: float = Field(gt=0, le=1)
    item_fit_ceiling_step: float = Field(gt=0, le=1)

    # Защита теста
    drift_shift: float
    drift_cusum_h: float
    rt_min_responses: int
    rt_hard_item_p: float
    rt_fast_z: float
    rt_flags_for_verification: int
    person_fit_lz: float
    focus_events_for_verification: int
    verification_items: int
    verification_time_limit_minutes: int
    verification_target_p: float
    verification_mismatch_z: float
    verification_retest_days: int

    # Профиль навыков и уровни доверия
    trust_weight_fsp: float
    trust_weight_verification: float
    trust_weight_test: float
    trust_weight_regular_task: float
    self_reported_stack_cap: float
    profile_decay_sd_per_year: float
    profile_stale_days: int
    topic_low_data_sd: float
    search_confident_sd: float

    # ФСП
    fsp_result_difficulty: dict[str, float]
    fsp_result_discrimination: float
    fsp_divergence_theta: float

    # Регулярные задания
    regular_task_rubric_offsets: dict[int, float]
    regular_task_discrimination: float

    # Подбор
    need_importance_weights: dict[str, float]
    need_key_topic_min_technologies: int
    nearby_grade_distance: int
    need_draft_confident: float = Field(ge=0, le=1)

    # Рынок
    invitation_weekly_budget: int
    invitation_ttl_days: int
    acceptance_target_probability: float
    # Медиана рынка по грейду, ₽ в месяц до НДФЛ.
    market_salary_median: dict[str, int]
    # Обучение модели принятия: CPU, сид и число потоков фиксированы — тот же сид, те же метрики.
    acceptance_model_iterations: int = Field(gt=0)
    acceptance_model_depth: int = Field(gt=0)
    acceptance_model_learning_rate: float = Field(gt=0)
    acceptance_model_random_seed: int
    acceptance_model_thread_count: int = Field(gt=0)
    salary_hint_rounding_rub: int
    message_max_length: int = Field(gt=0)

    # Обратная связь
    feedback_min_companies: int
    feedback_period_days: int
    feedback_hints_max: int
    feedback_min_gain: float

    # Резюме из PDF
    resume_max_bytes: int = Field(gt=0)
    resume_max_pages: int = Field(gt=0)
    resume_max_content_bytes: int = Field(gt=0)
    resume_min_font_pt: float = Field(ge=0)
    resume_max_lightness: float = Field(gt=0, le=1)
    resume_draft_confident: float = Field(ge=0, le=1)

    @field_validator("need_importance_weights")
    @classmethod
    def weight_for_every_importance(cls, value: dict[str, float]) -> dict[str, float]:
        """Вес темы — вес важности, нормированный на сумму: у каждой важности свой вес больше
        нуля, иначе у потребности из одних желательных тем делить не на что."""
        if set(value) != {"key", "important", "nice"} or min(value.values()) <= 0:
            raise ValueError("нужны веса key, important и nice, все больше нуля")
        return value

    @field_validator("market_salary_median")
    @classmethod
    def positive_market_salary(cls, value: dict[str, int]) -> dict[str, int]:
        """Признак модели принятия — логарифм вилки к медиане: медиана больше нуля."""
        if min(value.values(), default=0) <= 0:
            raise ValueError("медиана рынка по грейду — больше нуля")
        return value

    @field_validator("level_sd_inflation")
    @classmethod
    def positive_inflation(cls, value: float) -> float:
        """Поправка погрешности умножает σ модели: при нуле и ниже погрешности нет."""
        if value <= 0:
            raise ValueError("поправка погрешности — больше нуля")
        return value

    @field_validator("confidence_language_bands")
    @classmethod
    def three_ascending_bands(cls, value: list[float]) -> list[float]:
        """Три границы делят вероятность на четыре слова: «ниже», «скорее ниже», «скорее выше»,
        «уверенно выше»."""
        if len(value) != 3 or not 0 < value[0] < value[1] < value[2] < 1:
            raise ValueError("нужны три границы по возрастанию строго между 0 и 1")
        return value

    @field_validator("fsp_result_difficulty")
    @classmethod
    def difficulty_by_result_type(cls, value: dict[str, float]) -> dict[str, float]:
        """Сложность достижения ФСП — только по типу результата, без рейтинга мероприятий и
        дисциплин; результат лучше — сложность не ниже. Участник отбора — не наблюдение, его
        здесь нет."""
        if set(value) != {"winner", "prize", "finalist"}:
            raise ValueError("нужны сложности winner, prize и finalist — по типу результата")
        if not value["winner"] >= value["prize"] >= value["finalist"]:
            raise ValueError("сложность победителя не ниже призёра, призёра — не ниже финалиста")
        return value

    @model_validator(mode="after")
    def market_salary_for_every_grade(self) -> Self:
        """Признак модели принятия есть у кандидата любого грейда."""
        if set(self.market_salary_median) != set(self.grade_thresholds):
            raise ValueError("market_salary_median — по медиане на каждый грейд grade_thresholds")
        return self

    @model_validator(mode="after")
    def retry_is_shorter_than_change(self) -> Self:
        """Провал не сжигает попытку: повтор после провала ждёт не дольше, чем после смены."""
        if not 0 < self.grade_retry_interval_days <= self.grade_change_interval_days:
            raise ValueError(
                "grade_retry_interval_days — больше нуля и не больше grade_change_interval_days"
            )
        return self

    @classmethod
    def from_yaml(cls, path: Path) -> "Mechanics":
        with path.open(encoding="utf-8") as f:
            return cls.model_validate(yaml.safe_load(f))
