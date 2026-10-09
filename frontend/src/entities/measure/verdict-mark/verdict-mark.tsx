import type { Verdict } from "@/shared/api"
import { useTranslation } from "@/shared/i18n"
import { IconLabel, type IconName } from "@/shared/ui"

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
  readonly lowData?: boolean
}

export function VerdictMark({ verdict, lowData = false }: VerdictMarkProps) {
  const { t } = useTranslation("measure")
  if (lowData)
    return (
      <IconLabel icon="uncertainty" tone="secondary">
        {t("verdict.lowData")}
      </IconLabel>
    )
  return (
    <IconLabel icon={VERDICT_ICON[verdict]} tone={VERDICT_TONE[verdict]}>
      {t(`verdict.${verdict}`)}
    </IconLabel>
  )
}
