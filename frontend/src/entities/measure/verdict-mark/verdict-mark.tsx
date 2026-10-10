import type { Verdict } from "@/shared/api"
import { useTranslation } from "@/shared/i18n"
import { IconLabel, type IconName } from "@/shared/ui"
import { ProbabilityLabel } from "../probability-label/probability-label"

const VERDICT_ICON: Readonly<Record<Verdict, IconName>> = {
  confidently_above: "accepted",
  likely_above: "check",
  likely_below: "minus",
  below: "declined",
}

const VERDICT_TONE = {
  confidently_above: "accent",
  likely_above: "default",
  likely_below: "secondary",
  below: "secondary",
} as const satisfies Record<Verdict, "accent" | "default" | "secondary">

export interface VerdictMarkProps {
  readonly verdict: Verdict
  readonly probability: number
  readonly lowData?: boolean
}

export function VerdictMark({ verdict, probability, lowData = false }: VerdictMarkProps) {
  const { t } = useTranslation("measure")
  return (
    <IconLabel
      icon={lowData ? "uncertainty" : VERDICT_ICON[verdict]}
      tone={lowData ? "secondary" : VERDICT_TONE[verdict]}
    >
      <ProbabilityLabel
        value={probability}
        verdict={verdict}
        lowData={lowData}
        label={t("match.requirement")}
      />
    </IconLabel>
  )
}
