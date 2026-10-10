import { ProbabilityLabel } from "@/entities/measure"
import { PlanTopics } from "@/entities/vacancy-test"
import type { VacancyTest } from "@/shared/api"
import { useCatalogNames, useFormatters, useTranslation } from "@/shared/i18n"
import { staggerStyle } from "@/shared/motion"
import { IconLabel, Meter, StatusBadge, type StatusTone } from "@/shared/ui"
import styles from "./vacancy-test-result.module.css"

const TONE = {
  not_started: "neutral",
  in_progress: "progress",
  finished: "positive",
} as const satisfies Record<VacancyTest["status"], StatusTone>

export interface VacancyTestResultProps {
  readonly test: VacancyTest
}

export function VacancyTestResult({ test }: VacancyTestResultProps) {
  const { t } = useTranslation("vacancyTest")
  const names = useCatalogNames()
  const format = useFormatters()
  const result = test.result
  return (
    <section className={styles.panel} aria-label={t("title")}>
      <div className={styles.head}>
        <IconLabel icon="test" className={styles.heading}>
          {t("title")}
        </IconLabel>
        <StatusBadge
          tone={TONE[test.status]}
          icon={test.status === "finished" ? "accepted" : "pending"}
        >
          {t(`status.${test.status}`, { answered: test.answered, items: test.plan.items })}
        </StatusBadge>
      </div>
      {result === null ? (
        <PlanTopics plan={test.plan} />
      ) : (
        <>
          <Meter
            label={t("result.match")}
            value={result.match}
            valueText={format.percent(result.match)}
          />
          <ul className={styles.topics} aria-label={t("result.title")}>
            {result.topics.map((row, index) => (
              <li key={row.topic.code} className={styles.row} style={staggerStyle(index)}>
                <span className={styles.name}>{names.topic(row.topic)}</span>
                <span className={styles.correct}>
                  {t("result.correct", { correct: row.correct, answered: row.answered })}
                </span>
                <ProbabilityLabel value={row.probability} label={t("result.requirement")} />
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
