import type { ReactNode } from "react"
import { useSearchParams } from "react-router"
import { useCandidateSearch } from "@/entities/selection"
import type { SearchHit } from "@/shared/api"
import { useTranslation } from "@/shared/i18n"
import { Swap } from "@/shared/motion"
import { Button, EmptyState, IconLabel, LoadError, Skeleton } from "@/shared/ui"
import { SearchFilters } from "../search-filters/search-filters"
import { filtersOf, paramsOf, stateOf } from "../search-params"
import { SearchRow } from "../search-row/search-row"
import styles from "./candidate-search.module.css"

export interface CandidateSearchProps {
  readonly invite: (hit: SearchHit) => ReactNode
}

function Results({
  filters,
  invite,
}: {
  filters: ReturnType<typeof filtersOf>
  invite: CandidateSearchProps["invite"]
}) {
  const { t } = useTranslation("search")
  const query = useCandidateSearch(filters)
  if (filters === null)
    return (
      <EmptyState
        icon="candidates"
        title={t("empty.pickTitle")}
        description={t("empty.pickText")}
      />
    )
  if (query.isError)
    return (
      <LoadError
        error={query.error}
        onRetry={() => void query.refetch()}
        pending={query.isFetching}
      />
    )
  const first = query.data?.pages[0]
  if (first === undefined) return <Skeleton lines={6} />
  const hits = query.data?.pages.flatMap((page) => page.entries) ?? []
  if (hits.length === 0)
    return (
      <EmptyState icon="filter" title={t("empty.noneTitle")} description={t("empty.noneText")} />
    )
  return (
    <div className={styles.results} data-stale={query.isFetching && !query.isFetchingNextPage}>
      <p className={styles.summary}>
        <IconLabel icon="candidates" tone="secondary">
          {t("results.total", { count: first.total })}
        </IconLabel>
        {first.unconfirmed_total > 0 ? (
          <span className={styles.muted}>
            {t("results.unconfirmed", { count: first.unconfirmed_total })}
          </span>
        ) : null}
      </p>
      <ol className={styles.rows} aria-label={t("results.label")}>
        {hits.map((hit, index) => (
          <SearchRow
            key={hit.candidate_id}
            hit={hit}
            index={index}
            animate={index < first.entries.length}
            invite={invite(hit)}
          />
        ))}
      </ol>
      {query.hasNextPage ? (
        <div className={styles.more}>
          <Button
            variant="secondary"
            icon="chevron-down"
            pending={query.isFetchingNextPage}
            onClick={() => void query.fetchNextPage()}
          >
            {t("results.more")}
          </Button>
        </div>
      ) : null}
    </div>
  )
}

export function CandidateSearch({ invite }: CandidateSearchProps) {
  const [params, setParams] = useSearchParams()
  const state = stateOf(params)
  const filters = filtersOf(state)
  return (
    <div className={styles.layout}>
      <SearchFilters
        state={state}
        onChange={(next) => setParams(paramsOf(next), { replace: true })}
      />
      <Swap swapKey={filters === null ? "pick" : "results"} as="div" className={styles.main}>
        <Results filters={filters} invite={invite} />
      </Swap>
    </div>
  )
}
