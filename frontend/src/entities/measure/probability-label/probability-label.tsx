import type { Verdict } from "@/shared/api"
import { useTranslation } from "@/shared/i18n"
import styles from "./probability-label.module.css"

export interface ProbabilityLabelProps {
  readonly value: number
  readonly verdict?: Verdict | null
  readonly lowData?: boolean
  readonly label?: string
}

type ProbabilityBand = "under20" | "20to50" | "50to80" | "80plus"

function bandOf(value: number): ProbabilityBand {
  if (value < 0.2) return "under20"
  if (value < 0.5) return "20to50"
  if (value < 0.8) return "50to80"
  return "80plus"
}

export function ProbabilityLabel({
  value,
  verdict,
  lowData = false,
  label,
}: ProbabilityLabelProps) {
  const { t } = useTranslation("measure")
  const band = bandOf(value)
  const words = lowData
    ? t("verdict.lowData")
    : verdict === undefined || verdict === null
      ? t(`probability.words.${band}`)
      : t(`verdict.${verdict}`)
  const range = t(`probability.range.${band}`)
  const accessibleLabel = [label, range, words].filter(Boolean).join(": ")

  return (
    <span className={styles.label} data-probability-label title={accessibleLabel}>
      <span className={styles.range}>{range}</span>
      <span className={styles.words}>{words}</span>
    </span>
  )
}
