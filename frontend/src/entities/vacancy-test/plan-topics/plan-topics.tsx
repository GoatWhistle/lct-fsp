import type { VacancyTestPlan } from "@/shared/api"
import { useCatalogNames, useFormatters, useTranslation } from "@/shared/i18n"
import { staggerStyle } from "@/shared/motion"
import { Chip, IconLabel } from "@/shared/ui"
import styles from "./plan-topics.module.css"

export interface PlanTopicsProps {
  readonly plan: VacancyTestPlan
}

export function PlanTopics({ plan }: PlanTopicsProps) {
  const { t } = useTranslation(["vacancyTest", "catalog"])
  const names = useCatalogNames()
  const format = useFormatters()
  return (
    <section className={styles.plan} aria-label={t("topics")}>
      <div className={styles.head}>
        <IconLabel icon="test" className={styles.total}>
          {t("items", { count: plan.items })}
        </IconLabel>
        <IconLabel icon="measure" tone="secondary">
          {names.grade(plan.grade.code)}
        </IconLabel>
      </div>
      <ul className={styles.list}>
        {plan.topics.map((row, index) => (
          <li key={row.topic.code} className={styles.row} style={staggerStyle(index)}>
            <span className={styles.name}>{names.topic(row.topic)}</span>
            <Chip tone={row.importance === "key" ? "accent" : "neutral"}>
              {t(`catalog:importance.${row.importance}` as never)}
            </Chip>
            <span className={styles.weight}>
              {t("weight", { value: format.percent(row.weight) })}
            </span>
            <span className={styles.items}>{t("items", { count: row.items })}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}
