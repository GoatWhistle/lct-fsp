import { GradeRuler } from "@/entities/measure"
import type { HistoryEntry } from "@/shared/api"
import { useCatalogNames, useFormatters, useTranslation } from "@/shared/i18n"
import { staggerStyle } from "@/shared/motion"
import { Card, Icon, IconLabel, type IconName } from "@/shared/ui"
import styles from "./history-panel.module.css"

export interface HistoryPanelProps {
  readonly history: readonly HistoryEntry[]
  readonly motionIndex?: number
  readonly className?: string | undefined
}

type Outcome =
  | "stepDown"
  | "raised"
  | "confirmed"
  | "assigned"
  | "offered"
  | "none"
  | "kept"
  | "block"
  | "verification"
  | "mismatch"

const OUTCOME_ICON: Readonly<Record<Outcome, IconName>> = {
  stepDown: "chevron-down",
  raised: "accepted",
  confirmed: "accepted",
  assigned: "accepted",
  offered: "uncertainty",
  none: "declined",
  kept: "minus",
  block: "topic",
  verification: "verification",
  mismatch: "alert",
}

function outcomeOf(entry: HistoryEntry): Outcome {
  if (entry.outcome === "verification") return "verification"
  if (entry.outcome === "confirmed") return "confirmed"
  if (entry.outcome === "mismatch") return "mismatch"
  if (entry.event === "step_down") return "stepDown"
  if (entry.outcome === "assigned") {
    if (entry.purpose === "grade_up") return "raised"
    return entry.outcome_grade === entry.grade ? "confirmed" : "assigned"
  }
  if (entry.outcome === "offered") return "offered"
  if (entry.outcome === "no_category") return "none"
  if (entry.outcome === "not_passed") return "kept"
  return "block"
}

function Entry({ entry, index }: { readonly entry: HistoryEntry; readonly index: number }) {
  const { t } = useTranslation("overview")
  const names = useCatalogNames()
  const format = useFormatters()
  const outcome = outcomeOf(entry)
  const words = {
    grade: names.grade(entry.grade),
    outcome: names.grade(entry.outcome_grade ?? entry.grade),
  }
  return (
    <li className={styles.entry} style={staggerStyle(index)} data-outcome={outcome}>
      <span className={styles.marker} aria-hidden="true">
        <span className={styles.node}>
          <Icon name={OUTCOME_ICON[outcome]} size="sm" />
        </span>
        <span className={styles.line} />
      </span>
      <div className={styles.content}>
        <div className={styles.head}>
          <p className={styles.title}>{t(`history.outcome.${outcome}`, words)}</p>
          <time className={styles.date} dateTime={entry.at}>
            {format.date(entry.at)}
          </time>
        </div>
        {entry.purpose === null ? null : (
          <IconLabel icon="test" tone="secondary" className={styles.purpose}>
            {t(`history.purpose.${entry.purpose}`, words)}
          </IconLabel>
        )}
        {entry.overall === null ? null : <GradeRuler level={entry.overall} size="inline" caption />}
      </div>
    </li>
  )
}

export function HistoryPanel({ history, motionIndex, className }: HistoryPanelProps) {
  const { t } = useTranslation("overview")
  const entries = [...history].reverse()
  return (
    <Card title={t("history.title")} motionIndex={motionIndex} className={className}>
      <ol className={styles.timeline} aria-label={t("history.title")}>
        {entries.map((entry, index) => (
          <Entry key={`${entry.at}-${entry.event}`} entry={entry} index={index} />
        ))}
      </ol>
    </Card>
  )
}
