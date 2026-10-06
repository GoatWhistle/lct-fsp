"""Банк семейств заданий на все специализации и темы справочника (mechanics.md, §5).

Код семейства — `<тема>.<слаг>`, стабилен: на него ссылаются предъявления. Один генератор может
служить семействам разных тем (SQL у бэкенда, QA и данных), но семейства и их параметры —
разные. Грейд семейства — оценка эксперта: от него стартовые сложность и разделяющая сила (§2).
По теме — два якорных семейства, junior и middle: их параметры заморожены и держат шкалу (§7).

Выведенные семейства в выдачу не попадают, но по коду восстанавливаются: на них ссылаются
предъявления прошлых попыток.
"""

from collections.abc import Iterable, Sequence

from app.assessment.bank import (
    algorithms,
    automation,
    browser,
    cicd,
    concurrency,
    containers,
    dataframes,
    deep_learning,
    distributed,
    frameworks,
    frontend_testing,
    http,
    iac,
    javascript,
    linux,
    markup,
    ml,
    mlops,
    observability,
    performance,
    python_code,
    security,
    shell,
    sql,
    statistics,
    testing,
)
from app.assessment.bank.family import Family, Generator, Instance, same_answer

__all__ = [
    "BANK",
    "RETIRED",
    "Family",
    "Instance",
    "covers",
    "families_for_topics",
    "get_family",
    "same_answer",
]

# Семейство в таблице — генератор (слаг из его имени) или пара «слаг, генератор».
Entry = Generator | tuple[str, Generator]


def _slug(entry: Entry) -> tuple[str, Generator]:
    if isinstance(entry, tuple):
        return entry
    return entry.__name__.replace("_", "-"), entry


def _topic(
    topic: str,
    *,
    anchors: tuple[str, str],
    intern: Sequence[Entry],
    junior: Sequence[Entry],
    middle: Sequence[Entry],
    senior: Sequence[Entry],
) -> list[Family]:
    families = []
    for grade, entries in (
        ("intern", intern),
        ("junior", junior),
        ("middle", middle),
        ("senior", senior),
    ):
        for slug, generate in map(_slug, entries):
            families.append(Family(f"{topic}.{slug}", topic, grade, generate, slug in anchors))
    if {f.code for f in families if f.anchor} != {f"{topic}.{a}" for a in anchors}:
        raise ValueError(f"якоря темы {topic} — не семейства темы: {anchors}")
    return families


def _algorithms(topic: str) -> list[Family]:
    """Алгоритмы у бэкенда и фронтенда — одни генераторы, свои семейства."""
    return _topic(
        topic,
        anchors=("binary-search-probes", "topological-order"),
        intern=[
            ("range-count", algorithms.range_count),
            algorithms.stack_ops,
            algorithms.nested_loops,
        ],
        junior=[algorithms.binary_search_probes, algorithms.linear_probing, algorithms.dfs_order],
        middle=[
            ("bfs-order", algorithms.bfs_order),
            algorithms.topological_order,
            algorithms.log_loop,
            algorithms.pairs_count,
        ],
        senior=[algorithms.knapsack, algorithms.shortest_distances],
    )


def _sql(topic: str, *extra_junior: Entry) -> list[Family]:
    """SQL у бэкенда, QA и данных — одни генераторы, свои семейства."""
    return _topic(
        topic,
        anchors=("group-having-sum", "left-join-groups"),
        intern=[sql.sum_where, sql.order_limit, sql.like_between, sql.distinct_count],
        junior=[sql.case_when_sum, sql.group_having_sum, sql.null_aggregates, *extra_junior],
        middle=[sql.left_join_groups, sql.union_sums, sql.correlated_subquery, sql.exists_subquery],
        senior=[
            ("window-rank", sql.window_rank),
            sql.running_window,
            sql.lag_changes,
            sql.self_join,
        ],
    )


def _http_api(topic: str, *, security_checks: bool = False) -> list[Family]:
    """HTTP и API у бэкенда и QA — одни генераторы, свои семейства. У QA в теме и проверки
    безопасности API: у бэкенда они — в теме безопасности."""
    extra: dict[str, list[Entry]] = {"junior": [], "middle": [], "senior": []}
    if security_checks:
        extra = {
            "junior": [security.cookie_sending],
            "middle": [security.bucket_statuses],
            "senior": [security.jwt_checks, security.replay_window],
        }
    return _topic(
        topic,
        anchors=("idempotency", "etag-conditional"),
        intern=[http.status_codes, http.page_bounds, http.safe_methods],
        junior=[
            ("idempotency", http.idempotency),
            http.fixed_window,
            http.retry_backoff,
            *extra["junior"],
        ],
        middle=[
            http.etag_conditional,
            http.cache_revalidation,
            http.cors_preflight,
            *extra["middle"],
        ],
        senior=[
            http.optimistic_locking,
            http.timeout_budget,
            http.offset_drift_missed,
            *extra["senior"],
        ],
    )


BANK: tuple[Family, ...] = tuple(
    [
        # Бэкенд
        *_topic(
            "backend.programming",
            anchors=("list-slicing", "mutable-default"),
            intern=[
                ("int-arithmetic", python_code.arithmetic),
                python_code.string_methods,
                python_code.comprehension_filter,
            ],
            junior=[
                ("list-slicing", python_code.slicing),
                python_code.dict_counting,
                python_code.collatz_steps,
            ],
            middle=[
                ("mutable-default", python_code.mutable_default),
                python_code.closure_counter,
                python_code.generator_exhaustion,
            ],
            senior=[
                ("late-binding", python_code.late_binding),
                python_code.exception_finally,
                python_code.mro_super,
            ],
        ),
        *_algorithms("backend.algorithms"),
        *_sql("backend.databases"),
        *_http_api("backend.api"),
        *_topic(
            "backend.concurrency",
            anchors=("producer-consumer", "event-loop-order"),
            intern=[
                ("pool-rounds", concurrency.pool_rounds),
                concurrency.threads_join,
                concurrency.gather_total,
            ],
            junior=[concurrency.makespan, concurrency.producer_consumer, concurrency.amdahl],
            middle=[
                concurrency.as_completed_order,
                concurrency.event_loop_order,
                concurrency.semaphore_timeline,
                concurrency.deadlock_cycle,
            ],
            senior=[
                ("lost-update", concurrency.lost_update),
                concurrency.lost_update_wide,
                concurrency.cas_retries,
            ],
        ),
        *_topic(
            "backend.distributed",
            anchors=("lru-pattern", "hash-ring"),
            intern=[distributed.fifo_pattern, distributed.partition_counts, distributed.moved_keys],
            junior=[
                distributed.lru_pattern,
                distributed.ttl_pattern,
                distributed.consumer_assignment,
            ],
            middle=[
                distributed.redelivery,
                distributed.hash_ring,
                distributed.replica_reads,
                distributed.circuit_breaker,
            ],
            senior=[distributed.quorum_checks, distributed.vector_clock],
        ),
        *_topic(
            "backend.testing",
            anchors=("mock-calls", "fixture-teardown"),
            intern=[testing.assert_failures, testing.run_summary, testing.boundary_points],
            junior=[testing.mock_calls, testing.shared_state, testing.mutation_score],
            middle=[
                testing.fixture_teardown,
                testing.line_hits,
                testing.side_effects,
                testing.branch_cover_set,
            ],
            senior=[testing.kill_matrix, testing.flaky_retries],
        ),
        *_topic(
            "backend.security",
            anchors=("injection-rows", "path-traversal"),
            intern=[
                ("password-space", security.password_space),
                security.html_escape,
                security.password_policy,
            ],
            junior=[security.injection_rows, security.cookie_sending, security.hash_cost],
            middle=[security.bucket_statuses, security.rbac_decisions, security.path_traversal],
            senior=[security.jwt_checks, security.replay_window, security.timing_compare],
        ),
        # Фронтенд
        *_topic(
            "frontend.javascript",
            anchors=("default-sort", "closure-counter"),
            intern=[javascript.type_coercion, javascript.array_pipeline, javascript.destructuring],
            junior=[
                javascript.default_sort,
                javascript.loose_equality,
                javascript.var_let_loop,
                javascript.array_mutation,
                javascript.float_sums,
            ],
            middle=[javascript.closure_counter, javascript.promise_combinators],
            senior=[javascript.event_loop, javascript.await_timing],
        ),
        *_topic(
            "frontend.markup",
            anchors=("specificity", "flex-grow"),
            intern=[markup.box_width, markup.rem_em, markup.nth_child],
            junior=[markup.specificity, markup.margin_collapse, markup.media_queries],
            middle=[
                markup.flex_grow,
                markup.sibling_selectors,
                markup.absolute_position,
                markup.percent_padding,
            ],
            senior=[markup.flex_shrink, markup.grid_fr],
        ),
        *_topic(
            "frontend.frameworks",
            anchors=("state-batching", "effect-runs"),
            intern=[
                frameworks.list_render,
                frameworks.immutable_update,
                frameworks.reducer_actions,
            ],
            junior=[
                frameworks.state_batching,
                frameworks.key_remount,
                frameworks.context_consumers,
            ],
            middle=[
                frameworks.memo_rerenders,
                frameworks.effect_runs,
                frameworks.use_memo_recompute,
            ],
            senior=[frameworks.stale_closure, frameworks.keyed_diff, frameworks.batched_renders],
        ),
        *_topic(
            "frontend.browser",
            anchors=("event-propagation", "debounce-calls"),
            intern=[browser.same_origin, browser.url_resolution, browser.parallel_downloads],
            junior=[browser.cache_directives, browser.event_propagation, browser.long_tasks],
            middle=[
                browser.debounce_calls,
                browser.throttle_calls,
                browser.script_order,
                browser.service_worker,
            ],
            senior=[browser.critical_path, browser.layout_shift],
        ),
        *_algorithms("frontend.algorithms"),
        *_topic(
            "frontend.testing",
            anchors=("mock-returns", "rtl-queries"),
            intern=[
                frontend_testing.jest_matchers,
                frontend_testing.jest_focus,
                testing.boundary_points,
            ],
            junior=[
                frontend_testing.mock_returns,
                frontend_testing.visual_diff,
                frontend_testing.coverage_thresholds,
                testing.mutation_score,
            ],
            middle=[
                frontend_testing.rtl_queries,
                frontend_testing.test_shards,
                frontend_testing.playwright_retries,
            ],
            senior=[
                frontend_testing.fake_timers,
                frontend_testing.async_pitfalls,
                testing.flaky_retries,
            ],
        ),
        # Данные и ML
        *_topic(
            "data-ml.math",
            anchors=("variance-std", "bayes"),
            intern=[statistics.mean_median, statistics.combinatorics, statistics.dice_sum],
            junior=[
                statistics.variance_std,
                statistics.expected_value,
                statistics.conditional_table,
            ],
            middle=[
                statistics.bayes,
                statistics.binomial,
                statistics.z_score,
                statistics.matrix_product,
            ],
            senior=[statistics.pearson, statistics.gradient_step],
        ),
        *_sql("data-ml.sql"),
        *_topic(
            "data-ml.python",
            anchors=("groupby-sum", "merge-rows"),
            intern=[
                dataframes.comprehension_stats,
                dataframes.dict_grouping,
                dataframes.array_slicing,
            ],
            junior=[dataframes.pandas_filter, dataframes.groupby_sum, dataframes.broadcast_shape],
            middle=[
                dataframes.merge_rows,
                dataframes.missing_values,
                dataframes.rolling_mean,
                dataframes.pivot_cell,
            ],
            senior=[dataframes.view_or_copy, dataframes.int8_overflow],
        ),
        *_topic(
            "data-ml.ml",
            anchors=("precision-recall", "gini-split"),
            intern=[ml.majority_baseline, ml.one_hot_columns, ml.kfold_sizes],
            junior=[ml.precision_recall, ml.f1_score, ml.knn_predict],
            middle=[ml.gini_split, ml.kmeans_step, ml.linear_fit, ml.log_loss],
            senior=[ml.roc_auc, ml.ndcg_at_k],
        ),
        *_topic(
            "data-ml.deep-learning",
            anchors=("conv-shape", "cross-entropy"),
            intern=[
                deep_learning.dense_params,
                deep_learning.relu_forward,
                deep_learning.softmax_probs,
            ],
            junior=[
                deep_learning.conv_shape,
                deep_learning.conv_params,
                deep_learning.max_pool,
            ],
            middle=[
                deep_learning.cross_entropy,
                deep_learning.batchnorm,
                deep_learning.lr_schedule,
                deep_learning.receptive_field,
            ],
            senior=[deep_learning.backprop, deep_learning.attention_weights],
        ),
        *_topic(
            "data-ml.mlops",
            anchors=("registry-stages", "dag-duration"),
            intern=[mlops.split_sizes, mlops.batch_inference, mlops.cron_runs],
            junior=[mlops.replicas_needed, mlops.canary_requests, mlops.registry_stages],
            middle=[
                mlops.dag_duration,
                mlops.feature_freshness,
                mlops.degradation_alerts,
                mlops.spot_training_cost,
            ],
            senior=[mlops.psi_drift, mlops.ab_test_z],
        ),
        # QA
        *_topic(
            "qa.theory",
            anchors=("defect-lifecycle", "decision-rules"),
            intern=[testing.equivalence_members, testing.boundary_points, testing.traceability],
            junior=[
                testing.defect_lifecycle,
                testing.risk_order,
                testing.defect_removal,
                testing.mutation_score,
            ],
            middle=[
                testing.decision_rules,
                testing.branch_cover_set,
                testing.pairwise_coverage,
                testing.line_hits,
            ],
            senior=[testing.transition_switch, testing.kill_matrix, testing.flaky_retries],
        ),
        *_http_api("qa.api", security_checks=True),
        *_topic(
            "qa.automation",
            anchors=("xfail-outcomes", "conftest-override"),
            intern=[
                automation.collect_count,
                automation.stacked_count,
                automation.keyword_selection,
                testing.run_summary,
                testing.assert_failures,
            ],
            junior=[
                automation.marker_selection,
                automation.xfail_outcomes,
                automation.fixture_setups,
                testing.mock_calls,
                testing.shared_state,
            ],
            middle=[
                automation.conftest_override,
                automation.explicit_wait,
                testing.fixture_teardown,
                testing.side_effects,
                frontend_testing.playwright_retries,
            ],
            senior=[automation.parametrized_setups, automation.xdist_duration],
        ),
        *_sql("qa.databases", security.injection_rows),
        *_topic(
            "qa.performance",
            anchors=("littles-law", "percentile"),
            intern=[
                ("throughput", performance.throughput),
                performance.error_rate,
                performance.ramp_up,
            ],
            junior=[
                ("littles-law", performance.littles_law),
                performance.apdex,
                performance.capacity_headroom,
                concurrency.amdahl,
                observability.error_budget,
            ],
            middle=[
                ("percentile", performance.percentile),
                performance.percentile_linear,
                performance.pacing_rps,
                performance.queue_utilization,
                observability.counter_rate,
            ],
            senior=[("closed-model", performance.closed_model), performance.histogram_quantile],
        ),
        # DevOps
        *_topic(
            "devops.linux",
            anchors=("sort-uniq", "cidr-hosts"),
            intern=[linux.chmod_modes, linux.path_navigation, linux.load_average],
            junior=[linux.umask_perms, linux.sort_uniq, linux.listening_ports],
            middle=[
                linux.cidr_hosts,
                linux.subnet_membership,
                linux.handshake_latency,
                security.path_traversal,
            ],
            senior=[linux.firewall_rules, linux.longest_prefix],
        ),
        *_topic(
            "devops.containers",
            anchors=("build-cache", "rolling-update"),
            intern=[
                containers.port_mapping,
                containers.service_selector,
                containers.memory_units,
            ],
            junior=[
                containers.build_cache,
                containers.hpa_replicas,
                containers.crashloop_backoff,
                mlops.replicas_needed,
            ],
            middle=[
                containers.rolling_update,
                containers.pod_scheduling,
                containers.probe_restart,
            ],
            senior=[containers.cpu_throttling, containers.pdb_disruptions],
        ),
        *_topic(
            "devops.ci-cd",
            anchors=("cache-key-hits", "needs-dag"),
            intern=[cicd.stage_duration, cicd.semver_bump, cicd.pipeline_minutes],
            junior=[cicd.rules_first_match, cicd.cache_key_hits, mlops.canary_requests],
            middle=[
                cicd.needs_dag,
                cicd.matrix_jobs,
                cicd.dora_metrics,
                frontend_testing.test_shards,
            ],
            senior=[cicd.helm_rollback, cicd.flaky_pipeline, automation.xdist_duration],
        ),
        *_topic(
            "devops.iac",
            anchors=("var-precedence", "cidrsubnet"),
            intern=[iac.plan_symbols, iac.resource_count],
            junior=[iac.var_precedence, iac.ansible_idempotency, iac.loop_when],
            middle=[iac.count_vs_for_each, iac.cidrsubnet, iac.tf_expressions, iac.ansible_vars],
            senior=[iac.moved_refactor, iac.ansible_serial],
        ),
        *_topic(
            "devops.observability",
            anchors=("error-budget", "counter-rate"),
            intern=[
                performance.error_rate,
                observability.log_retention,
                observability.label_cardinality,
            ],
            junior=[
                observability.error_budget,
                observability.availability_chain,
                performance.apdex,
            ],
            middle=[
                performance.percentile,
                observability.counter_rate,
                observability.alert_for,
                mlops.degradation_alerts,
            ],
            senior=[
                observability.burn_rate,
                performance.histogram_quantile,
                observability.trace_sampling,
            ],
        ),
        *_topic(
            "devops.scripting",
            anchors=("test-conditions", "param-expansion"),
            intern=[
                shell.seq_loop,
                python_code.string_methods,
                linux.grep_count,
                mlops.cron_runs,
            ],
            junior=[shell.test_conditions, linux.exit_chain, python_code.dict_counting],
            middle=[shell.param_expansion, shell.awk_sum, shell.find_filters],
            senior=[shell.errexit, shell.word_splitting, python_code.exception_finally],
        ),
    ]
)

# Выведены из выдачи: верные ответы двух экземпляров совпадают чаще, чем допускает
# `family_answer_collision_max`. Замена — семейства с ответом из нескольких значений.
RETIRED: tuple[Family, ...] = tuple(
    Family(code, code.rsplit(".", 1)[0], grade, generate)
    for code, grade, generate in [
        ("backend.algorithms.binary-search-steps", "junior", algorithms.binary_search_steps),
        ("backend.algorithms.shortest-path", "senior", algorithms.shortest_path),
        ("backend.databases.count-where", "intern", sql.count_where),
        ("backend.databases.group-having", "junior", sql.group_having),
        ("backend.databases.left-join-on", "middle", sql.left_join_on),
        ("backend.api.status-code", "intern", http.status_code),
        ("backend.api.pagination", "middle", http.pagination),
        ("backend.api.cache-max-age", "senior", http.cache_max_age),
        ("backend.concurrency.asyncio-gather", "junior", concurrency.asyncio_gather),
        ("backend.concurrency.pool-makespan", "middle", concurrency.pool_makespan),
        ("backend.distributed.cache-hits", "intern", distributed.cache_hits),
        ("backend.distributed.lru-hits", "junior", distributed.lru_hits),
        ("backend.distributed.rehash-moves", "middle", distributed.rehash_moves),
        ("backend.distributed.quorum", "senior", distributed.quorum),
        ("backend.testing.fail-fast", "intern", testing.fail_fast),
        ("backend.testing.boundary-values", "junior", testing.boundary_values),
        ("backend.testing.branch-coverage", "middle", testing.branch_coverage),
        ("backend.testing.mutant-killers", "senior", testing.mutant_killers),
        ("backend.security.sql-injection", "junior", security.sql_injection),
        ("backend.security.token-bucket", "middle", security.token_bucket),
        ("backend.security.jwt-validity", "senior", security.jwt_validity),
        ("qa.theory.equivalence-class", "intern", testing.equivalence_class),
        ("qa.theory.boundary-values", "junior", testing.boundary_values),
        ("qa.theory.decision-table", "middle", testing.decision_table),
        ("qa.theory.transition-pairs", "senior", testing.transition_pairs),
        ("qa.api.status-code", "intern", http.status_code),
        ("qa.api.pagination", "middle", http.pagination),
        ("qa.api.offset-drift", "senior", http.offset_drift),
        ("qa.automation.parametrize-count", "intern", automation.parametrize_count),
        ("qa.automation.stacked-parametrize", "junior", automation.stacked_parametrize),
        ("qa.automation.fixture-scope", "middle", automation.fixture_scope),
        ("qa.automation.parametrized-fixture", "senior", automation.parametrized_fixture),
        ("qa.databases.count-where", "intern", sql.count_where),
        ("qa.databases.group-having", "junior", sql.group_having),
        ("qa.databases.left-join-on", "middle", sql.left_join_on),
    ]
)

_BY_CODE = {family.code: family for family in (*BANK, *RETIRED)}


def get_family(code: str) -> Family:
    return _BY_CODE[code]


def families_for_topics(topics: Iterable[str]) -> list[Family]:
    """Семейства тем в выдаче — без выведенных."""
    wanted = set(topics)
    return [family for family in BANK if family.topic in wanted]


def covers(topics: Iterable[str]) -> bool:
    """Есть ли семейства на каждую тему — без этого тест по специализации не собрать."""
    present = {family.topic for family in BANK}
    return all(topic in present for topic in topics)
