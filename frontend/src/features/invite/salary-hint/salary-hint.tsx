import { ProbabilityLabel } from "@/entities/measure"
import { useSalaryHint } from "@/entities/selection"
import { useFormatters, useMoneyRange, useTranslation } from "@/shared/i18n"
import { Banner, Button } from "@/shared/ui"
import styles from "./salary-hint.module.css"

export interface SalaryHintProps {
  readonly selectionId: string | null
  readonly candidateId: string
  readonly from: number | null
  readonly to: number | null
  readonly onApply: (from: number, to: number) => void
}

export function SalaryHint({ selectionId, candidateId, from, to, onApply }: SalaryHintProps) {
  const { t } = useTranslation("selection")
  const format = useFormatters()
  const range = useMoneyRange()
  const { data } = useSalaryHint(selectionId, candidateId, from, to)
  if (data === undefined || !data.available) return null
  const { probability, target_probability: target, hint_from: hintFrom, hint_to: hintTo } = data
  if (probability === null || target === null || data.rounding === null) return null
  const reached = probability >= target
  const apply =
    reached || hintFrom === null || hintTo === null ? undefined : (
      <Button size="compact" variant="secondary" onClick={() => onApply(hintFrom, hintTo)}>
        {t("invite.hint.apply")}
      </Button>
    )
  return (
    <Banner
      tone={reached ? "info" : "attention"}
      icon="match"
      title={t("invite.hint.probability", { range: range(data.evaluated_from, data.evaluated_to) })}
      action={apply}
      className={styles.hint}
    >
      <p>
        <ProbabilityLabel value={probability} label={t("invite.hint.current")} />
      </p>
      <p>
        {hintFrom === null
          ? t("invite.hint.unreachable")
          : t(reached ? "invite.hint.enough" : "invite.hint.suggest", {
              range: range(hintFrom, hintTo),
            })}{" "}
        <ProbabilityLabel value={target} label={t("invite.hint.target")} />
      </p>
      <p className={styles.note}>
        {t("invite.hint.rounding", { step: format.money(data.rounding) })}
      </p>
    </Banner>
  )
}
