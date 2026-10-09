import { type KeyboardEvent, type ReactNode, useEffect, useRef } from "react"
import type { SelectionEntry } from "@/shared/api"
import { useTranslation } from "@/shared/i18n"
import { Button, IconLabel } from "@/shared/ui"
import { ResultRow } from "../result-row/result-row"
import { BLOCKS } from "../selection-model"
import styles from "./result-list.module.css"

export interface ResultListProps {
  readonly entries: readonly SelectionEntry[]
  readonly stackCap: number
  readonly selected: string | null
  readonly shortlist: ReadonlySet<string>
  readonly animateCount: number
  readonly stale: boolean
  readonly hasMore: boolean
  readonly loadingMore: boolean
  readonly onLoadMore: () => void
  readonly onSelect: (id: string) => void
  readonly onToggleShortlist: (id: string, on: boolean) => void
  readonly invite: (entry: SelectionEntry) => ReactNode
}

function isTyping(target: EventTarget | null): boolean {
  return target instanceof HTMLElement && target.closest("input, textarea, [role=dialog]") !== null
}

export function ResultList(props: ResultListProps) {
  const { entries, selected, shortlist, onSelect, onToggleShortlist } = props
  const { t } = useTranslation("selection")
  const listRef = useRef<HTMLElement | null>(null)

  const focusRow = (index: number) => {
    const entry = entries[index]
    if (entry === undefined) return
    listRef.current
      ?.querySelector<HTMLButtonElement>(`[data-candidate="${entry.candidate_id}"]`)
      ?.focus()
    onSelect(entry.candidate_id)
  }

  const onRowKey = (index: number) => (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault()
      focusRow(index + (event.key === "ArrowDown" ? 1 : -1))
    }
  }

  useEffect(() => {
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (event.key.toLowerCase() !== "s" || event.ctrlKey || event.metaKey || event.altKey) return
      if (isTyping(event.target) || selected === null) return
      event.preventDefault()
      onToggleShortlist(selected, !shortlist.has(selected))
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [selected, shortlist, onToggleShortlist])

  return (
    <section
      ref={listRef}
      className={styles.list}
      data-stale={props.stale}
      aria-busy={props.stale}
      aria-label={t("list.label")}
    >
      <p className={styles.keys}>
        <IconLabel icon="keyboard" tone="secondary">
          {t("list.keys")}
        </IconLabel>
      </p>
      {BLOCKS.map((block) => {
        const rows = entries.filter((entry) => entry.block === block)
        if (rows.length === 0) return null
        return (
          <section
            key={block}
            className={styles.block}
            data-block={block}
            aria-label={t(`selection:blocks.${block}` as never)}
          >
            <div className={styles.divider} aria-hidden="true">
              <span className={styles.node} />
              <span className={styles.blockTitle}>{t(`selection:blocks.${block}` as never)}</span>
              <span className={styles.line} />
            </div>
            <ol className={styles.rows}>
              {rows.map((entry) => {
                const index = entries.indexOf(entry)
                return (
                  <ResultRow
                    key={entry.candidate_id}
                    entry={entry}
                    index={index}
                    stackCap={props.stackCap}
                    selected={selected === entry.candidate_id}
                    shortlisted={shortlist.has(entry.candidate_id)}
                    animate={index < props.animateCount}
                    invite={props.invite(entry)}
                    onSelect={() => onSelect(entry.candidate_id)}
                    onToggleShortlist={() =>
                      onToggleShortlist(entry.candidate_id, !shortlist.has(entry.candidate_id))
                    }
                    onKeyDown={onRowKey(index)}
                  />
                )
              })}
            </ol>
          </section>
        )
      })}
      {props.hasMore ? (
        <div className={styles.more}>
          <Button
            variant="secondary"
            icon="chevron-down"
            pending={props.loadingMore}
            onClick={props.onLoadMore}
          >
            {t("list.more")}
          </Button>
        </div>
      ) : null}
    </section>
  )
}
