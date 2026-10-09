import type { KeyboardEvent, ReactNode } from "react"
import { MatchScore, TrustBadge } from "@/entities/measure"
import { anonymousId } from "@/entities/selection"
import type { SelectionEntry } from "@/shared/api"
import { useCatalogNames, useFormatters, useTranslation } from "@/shared/i18n"
import { staggerStyle } from "@/shared/motion"
import { Button, Icon, IconLabel, PlainButton, Tooltip } from "@/shared/ui"
import { hasFsp } from "../selection-model"
import styles from "./result-row.module.css"

export interface ResultRowProps {
  readonly entry: SelectionEntry
  readonly index: number
  readonly stackCap: number
  readonly selected: boolean
  readonly shortlisted: boolean
  readonly animate: boolean
  readonly invite: ReactNode
  readonly onSelect: () => void
  readonly onToggleShortlist: () => void
  readonly onKeyDown: (event: KeyboardEvent<HTMLButtonElement>) => void
}

export function ResultRow({
  entry,
  index,
  stackCap,
  selected,
  shortlisted,
  animate,
  invite,
  onSelect,
  onToggleShortlist,
  onKeyDown,
}: ResultRowProps) {
  const { t } = useTranslation(["selection", "measure"])
  const names = useCatalogNames()
  const format = useFormatters()
  const id = anonymousId(entry.candidate_id)
  const status = entry.grade_status
  const statusText =
    status.kind === "confirmed"
      ? t("measure:gradeStatus.confirmed")
      : t(`measure:gradeStatus.${status.kind}` as never, {
          claimed: names.grade(status.claimed),
          confirmed: status.confirmed === null ? "" : names.grade(status.confirmed),
        })

  return (
    <li
      className={styles.row}
      data-block={entry.block}
      data-selected={selected}
      data-animate={animate}
      style={staggerStyle(index)}
    >
      <PlainButton
        className={styles.main}
        aria-current={selected ? "true" : undefined}
        data-candidate={entry.candidate_id}
        onClick={onSelect}
        onKeyDown={onKeyDown}
      >
        <span className={styles.position}>{entry.position}</span>
        <span className={styles.identity}>
          <span className={styles.id}>{id}</span>
          <span className={styles.status}>
            <IconLabel
              icon={status.kind === "confirmed" ? "test" : "alert"}
              tone={status.kind === "confirmed" ? "secondary" : "danger"}
              className={styles.statusText}
            >
              {statusText}
            </IconLabel>
            {entry.stale ? (
              <Tooltip content={t("row.stale")}>
                <span className={styles.stale} aria-label={t("row.stale")} role="img">
                  <Icon name="clock" size="sm" />
                </span>
              </Tooltip>
            ) : null}
          </span>
        </span>
        <span className={styles.score}>
          {entry.match_score === null ? (
            <span className={styles.muted}>{t("row.noScore")}</span>
          ) : (
            <MatchScore
              score={entry.match_score}
              topics={entry.topics}
              stack={entry.stack}
              stackCap={stackCap}
              size="sm"
              animate={animate}
            />
          )}
        </span>
        <span className={styles.facts}>
          {entry.acceptance_probability === null ? null : (
            <span className={styles.fact}>
              <Icon name="accepted" size="sm" />
              <span>
                {t("row.acceptance")}{" "}
                <strong>{format.percent(entry.acceptance_probability)}</strong>
              </span>
            </span>
          )}
          <span className={styles.fact}>
            <Icon name="test" size="sm" />
            {t("row.stack", { matched: entry.stack.matched.length, total: entry.stack.total })}
          </span>
          {hasFsp(entry) ? <TrustBadge source="fsp" /> : null}
        </span>
      </PlainButton>
      <span className={styles.actions}>
        {invite}
        <Button
          variant="ghost"
          size="icon"
          icon="star"
          className={styles.star}
          data-on={shortlisted}
          aria-pressed={shortlisted}
          aria-label={shortlisted ? t("row.shortlistRemove") : t("row.shortlistAdd")}
          onClick={onToggleShortlist}
        >
          {null}
        </Button>
      </span>
    </li>
  )
}
