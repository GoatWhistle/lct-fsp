"""Банк семейств заданий: по одному семейству на каждый грейд каждой темы бэкенда и QA.

Код семейства — `<тема>.<слаг>`, стабилен: на него ссылаются предъявления. Один генератор может
служить семействам разных тем (SQL у бэкенда и QA), но семейства и их параметры — разные.
Полный банк на все специализации — задача адаптивного теста (lct-9).
"""

from collections.abc import Iterable

from app.assessment.bank import (
    algorithms,
    automation,
    concurrency,
    distributed,
    http,
    performance,
    python_code,
    security,
    sql,
    testing,
)
from app.assessment.bank.family import Family, Generator, Instance, same_answer

__all__ = [
    "BANK",
    "Family",
    "Instance",
    "covers",
    "families_for_topics",
    "get_family",
    "same_answer",
]

GRADES = ("intern", "junior", "middle", "senior")


def _topic(topic: str, *generators: tuple[str, Generator]) -> list[Family]:
    """Семейства темы от стажёра к senior: по одному на грейд."""
    return [
        Family(f"{topic}.{slug}", topic, grade, generate)
        for grade, (slug, generate) in zip(GRADES, generators, strict=True)
    ]


BANK: tuple[Family, ...] = tuple(
    [
        *_topic(
            "backend.programming",
            ("int-arithmetic", python_code.arithmetic),
            ("list-slicing", python_code.slicing),
            ("mutable-default", python_code.mutable_default),
            ("late-binding", python_code.late_binding),
        ),
        *_topic(
            "backend.algorithms",
            ("range-count", algorithms.range_count),
            ("binary-search-steps", algorithms.binary_search_steps),
            ("bfs-order", algorithms.bfs_order),
            ("shortest-path", algorithms.shortest_path),
        ),
        *_topic(
            "backend.databases",
            ("count-where", sql.count_where),
            ("group-having", sql.group_having),
            ("left-join-on", sql.left_join_on),
            ("window-rank", sql.window_rank),
        ),
        *_topic(
            "backend.api",
            ("status-code", http.status_code),
            ("idempotency", http.idempotency),
            ("pagination", http.pagination),
            ("cache-max-age", http.cache_max_age),
        ),
        *_topic(
            "backend.concurrency",
            ("pool-rounds", concurrency.pool_rounds),
            ("asyncio-gather", concurrency.asyncio_gather),
            ("pool-makespan", concurrency.pool_makespan),
            ("lost-update", concurrency.lost_update),
        ),
        *_topic(
            "backend.distributed",
            ("cache-hits", distributed.cache_hits),
            ("lru-hits", distributed.lru_hits),
            ("rehash-moves", distributed.rehash_moves),
            ("quorum", distributed.quorum),
        ),
        *_topic(
            "backend.testing",
            ("fail-fast", testing.fail_fast),
            ("boundary-values", testing.boundary_values),
            ("branch-coverage", testing.branch_coverage),
            ("mutant-killers", testing.mutant_killers),
        ),
        *_topic(
            "backend.security",
            ("password-space", security.password_space),
            ("sql-injection", security.sql_injection),
            ("token-bucket", security.token_bucket),
            ("jwt-validity", security.jwt_validity),
        ),
        *_topic(
            "qa.theory",
            ("equivalence-class", testing.equivalence_class),
            ("boundary-values", testing.boundary_values),
            ("decision-table", testing.decision_table),
            ("transition-pairs", testing.transition_pairs),
        ),
        *_topic(
            "qa.api",
            ("status-code", http.status_code),
            ("idempotency", http.idempotency),
            ("pagination", http.pagination),
            ("offset-drift", http.offset_drift),
        ),
        *_topic(
            "qa.automation",
            ("parametrize-count", automation.parametrize_count),
            ("stacked-parametrize", automation.stacked_parametrize),
            ("fixture-scope", automation.fixture_scope),
            ("parametrized-fixture", automation.parametrized_fixture),
        ),
        *_topic(
            "qa.databases",
            ("count-where", sql.count_where),
            ("group-having", sql.group_having),
            ("left-join-on", sql.left_join_on),
            ("window-rank", sql.window_rank),
        ),
        *_topic(
            "qa.performance",
            ("throughput", performance.throughput),
            ("littles-law", performance.littles_law),
            ("percentile", performance.percentile),
            ("closed-model", performance.closed_model),
        ),
    ]
)

_BY_CODE = {family.code: family for family in BANK}


def get_family(code: str) -> Family:
    return _BY_CODE[code]


def families_for_topics(topics: Iterable[str]) -> list[Family]:
    wanted = set(topics)
    return [family for family in BANK if family.topic in wanted]


def covers(topics: Iterable[str]) -> bool:
    """Есть ли семейства на каждую тему — без этого тест по специализации не собрать."""
    present = {family.topic for family in BANK}
    return all(topic in present for topic in topics)
