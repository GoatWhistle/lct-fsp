import { type ReactNode, useCallback, useMemo, useState } from "react"
import { useSearchParams } from "react-router"
import { useTechnologies } from "@/entities/catalog"
import {
  anonymousId,
  useApplyFilters,
  useSelection,
  useToggleShortlist,
} from "@/entities/selection"
import type { CandidateFilters, Selection, SelectionEntry, Technology } from "@/shared/api"
import { useMediaQuery } from "@/shared/hooks"
import { useErrorText, useTranslation } from "@/shared/i18n"
import {
  Button,
  type ComboboxOption,
  Dialog,
  EmptyState,
  LoadError,
  Skeleton,
  toast,
} from "@/shared/ui"
import { ExplanationPanel } from "../explanation-panel/explanation-panel"
import { FiltersPanel, isFiltered } from "../filters-panel/filters-panel"
import { ResultList } from "../result-list/result-list"
import { SelectionBar } from "../selection-bar/selection-bar"
import { entriesOf } from "../selection-model"
import { ShortlistDrawer } from "../shortlist-drawer/shortlist-drawer"
import styles from "./selection-board.module.css"

const EMPTY_FILTERS: CandidateFilters = {
  fsp_confirmed: false,
  confident: false,
  stack: [],
  grade_status: [],
}

function stackOptions(
  technologies: readonly Technology[] | undefined,
  specialization: string,
): ComboboxOption[] {
  return (technologies ?? [])
    .filter((tech) => tech.topics.some((topic) => topic.startsWith(`${specialization}.`)))
    .map((tech) => ({ value: tech.code, label: tech.name }))
}

function NoResults({ filtered }: { readonly filtered: boolean }) {
  const { t } = useTranslation("selection")
  return (
    <EmptyState
      icon={filtered ? "filter" : "candidates"}
      title={filtered ? t("list.emptyTitle") : t("list.noneTitle")}
      description={filtered ? t("list.emptyText") : t("list.noneText")}
    />
  )
}

export interface SelectionBoardProps {
  readonly selectionId: string
  readonly invite: (entry: SelectionEntry, selection: Selection) => ReactNode
}

export function SelectionBoard({ selectionId, invite }: SelectionBoardProps) {
  const { t } = useTranslation("selection")
  const errorText = useErrorText()
  const query = useSelection(selectionId)
  const apply = useApplyFilters(selectionId)
  const toggle = useToggleShortlist(selectionId)
  const technologies = useTechnologies()
  const [params, setParams] = useSearchParams()
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [shortlistOpen, setShortlistOpen] = useState(false)
  const wide = useMediaQuery("(min-width: 120rem)")
  const sideExplain = useMediaQuery("(min-width: 64rem)")
  const first = query.data?.pages[0]
  const entries = useMemo(() => entriesOf(query.data), [query.data])
  const selected = params.get("candidate")
  const current = entries.find((entry) => entry.candidate_id === selected) ?? null
  const shortlist = useMemo(() => new Set(first?.shortlist ?? []), [first?.shortlist])

  const select = useCallback(
    (id: string | null) =>
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          if (id === null) next.delete("candidate")
          else next.set("candidate", id)
          return next
        },
        { replace: true },
      ),
    [setParams],
  )
  const onToggle = useCallback(
    (candidate: string, on: boolean) =>
      toggle.mutate({ candidate, on }, { onError: (error) => toast.error(errorText(error)) }),
    [toggle, errorText],
  )

  if (query.isError)
    return (
      <LoadError
        error={query.error}
        onRetry={() => void query.refetch()}
        pending={query.isFetching}
      />
    )
  if (first === undefined) return <Skeleton shape="block" />

  const filters: CandidateFilters = { ...EMPTY_FILTERS, ...first.filters }
  const setFilters = (next: CandidateFilters) =>
    apply.mutate(next, { onError: (error) => toast.error(errorText(error)) })
  const panel = (
    <FiltersPanel
      filters={filters}
      stackOptions={stackOptions(technologies.data, first.specialization.code)}
      pending={apply.isPending}
      onChange={setFilters}
      onReset={() => setFilters(EMPTY_FILTERS)}
    />
  )
  const explanation = (framed: boolean) => (
    <ExplanationPanel
      entry={current}
      stackCap={first.stack_cap}
      invite={current === null ? null : invite(current, first)}
      onClose={() => select(null)}
      framed={framed}
    />
  )

  return (
    <div className={styles.board} data-wide={wide}>
      <div className={styles.bar}>
        <SelectionBar
          selection={first}
          shortlistCount={shortlist.size}
          onOpenShortlist={() => setShortlistOpen(true)}
        />
        {wide ? null : (
          <Button
            variant="secondary"
            size="compact"
            icon="filter"
            onClick={() => setFiltersOpen(true)}
          >
            {t("filters.title")}
          </Button>
        )}
      </div>
      {wide ? <div className={styles.filters}>{panel}</div> : null}
      <div className={styles.results}>
        {entries.length === 0 ? (
          <NoResults filtered={isFiltered(filters)} />
        ) : (
          <ResultList
            entries={entries}
            stackCap={first.stack_cap}
            selected={selected}
            shortlist={shortlist}
            animateCount={first.entries.length}
            stale={apply.isPending}
            hasMore={query.hasNextPage}
            loadingMore={query.isFetchingNextPage}
            onLoadMore={() => void query.fetchNextPage()}
            onSelect={select}
            onToggleShortlist={onToggle}
            invite={(entry) => invite(entry, first)}
          />
        )}
      </div>
      {sideExplain ? <div className={styles.explain}>{explanation(true)}</div> : null}
      <Dialog
        open={!wide && filtersOpen}
        onClose={() => setFiltersOpen(false)}
        size="drawer"
        title={t("filters.title")}
      >
        {panel}
      </Dialog>
      <Dialog
        open={!sideExplain && current !== null}
        onClose={() => select(null)}
        size="drawer"
        title={
          current === null
            ? t("explain.title")
            : t("explain.titleFor", { id: anonymousId(current.candidate_id) })
        }
      >
        {explanation(false)}
      </Dialog>
      <ShortlistDrawer
        selectionId={selectionId}
        stackCap={first.stack_cap}
        open={shortlistOpen}
        onClose={() => setShortlistOpen(false)}
        onPick={(id) => {
          setShortlistOpen(false)
          select(id)
        }}
      />
    </div>
  )
}
