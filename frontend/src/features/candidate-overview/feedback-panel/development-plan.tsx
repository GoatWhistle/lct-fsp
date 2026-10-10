import { useDevelopmentPlan } from "@/entities/profile"
import { BackendText, useCatalogNames, useTranslation } from "@/shared/i18n"
import { staggerStyle } from "@/shared/motion"
import { IconLabel } from "@/shared/ui"
import styles from "./development-plan.module.css"

export function DevelopmentPlan() {
  const { t } = useTranslation("overview")
  const names = useCatalogNames()
  const plan = useDevelopmentPlan(true)
  if (plan.data === undefined || plan.data === null) return null
  return (
    <section className={styles.plan} aria-label={t("feedback.plan")}>
      <IconLabel icon="llm" className={styles.title}>
        {t("feedback.plan")}
      </IconLabel>
      <ol className={styles.steps}>
        {plan.data.steps.map((step, index) => (
          <li
            key={`${step.topic}-${step.step}`}
            className={styles.step}
            style={staggerStyle(index)}
          >
            <span className={styles.topic}>
              {names.topic({ code: step.topic, name: step.topic })}
            </span>
            <BackendText>{step.step}</BackendText>
          </li>
        ))}
      </ol>
    </section>
  )
}
