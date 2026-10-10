import { ProbabilityLabel } from "@/entities/measure"
import type { SelectionEntry } from "@/shared/api"
import { useFormatters, useTranslation } from "@/shared/i18n"
import { Meter } from "@/shared/ui"
import { factorBars } from "../selection-model"
import styles from "./acceptance-part.module.css"

export interface AcceptancePartProps {
  readonly entry: SelectionEntry
}

export function AcceptancePart({ entry }: AcceptancePartProps) {
  const { t } = useTranslation("selection")
  const format = useFormatters()
  const why = entry.acceptance_explanation
  if (why === null || entry.acceptance_probability === null) return null
  return (
    <section className={styles.section} aria-label={t("explain.acceptance")}>
      <p className={styles.subtitle}>{t("explain.acceptance")}</p>
      <p className={styles.lead}>
        {t("explain.acceptanceLead")}{" "}
        <ProbabilityLabel value={entry.acceptance_probability} label={t("explain.acceptance")} />
      </p>
      <ul className={styles.factors}>
        {factorBars(why).map((bar) => (
          <li key={bar.factor}>
            <Meter
              label={t(`explain.factors.${bar.factor}` as never)}
              value={bar.share}
              valueText={t("explain.factorValue", { value: format.number(bar.contribution, 2) })}
              tone={bar.contribution < 0 ? "attention" : "default"}
            />
          </li>
        ))}
      </ul>
      <p className={styles.muted}>
        {t("explain.acceptanceBase", {
          base: format.number(why.base, 2),
          logit: format.number(why.logit, 2),
        })}
      </p>
    </section>
  )
}
