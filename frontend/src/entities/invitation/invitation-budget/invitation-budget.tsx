import { clsx } from "clsx"
import type { InvitationBudget as Budget } from "@/shared/api"
import { useFormatters, useTranslation } from "@/shared/i18n"
import { IconLabel, Meter } from "@/shared/ui"
import styles from "./invitation-budget.module.css"

export interface InvitationBudgetProps {
  readonly budget: Budget
  readonly className?: string | undefined
}

export function InvitationBudget({ budget, className }: InvitationBudgetProps) {
  const { t } = useTranslation("employer")
  const format = useFormatters()
  const ratio = budget.limit === 0 ? 0 : budget.remaining / budget.limit
  return (
    <div className={clsx(styles.budget, className)}>
      <Meter
        label={t("budget.label")}
        value={ratio}
        valueText={t("budget.left", { left: budget.remaining, limit: budget.limit })}
        tone={budget.remaining === 0 ? "attention" : "default"}
      />
      <IconLabel icon="calendar" tone="secondary" size="sm" className={styles.resets}>
        {t("budget.resets", { date: format.dateMoscow(budget.resets_at) })}
      </IconLabel>
    </div>
  )
}
