import { PlanTopics, useVacancyTestPreview } from "@/entities/vacancy-test"
import { useTranslation } from "@/shared/i18n"
import { Swap } from "@/shared/motion"
import { Button, IconLabel, LoadError, Skeleton } from "@/shared/ui"
import { ExampleCard } from "../example-card/example-card"
import styles from "./vacancy-test-preview.module.css"

export interface VacancyTestPreviewProps {
  readonly needId: string
}

export function VacancyTestPreview({ needId }: VacancyTestPreviewProps) {
  const { t } = useTranslation("vacancyTest")
  const preview = useVacancyTestPreview(needId)
  if (preview.isError)
    return (
      <LoadError
        error={preview.error}
        onRetry={() => void preview.refetch()}
        pending={preview.isFetching}
      />
    )
  if (preview.data === undefined)
    return (
      <div className={styles.preview} aria-busy="true">
        <Skeleton lines={3} />
        <Skeleton shape="block" />
      </div>
    )
  const { plan, examples } = preview.data
  return (
    <div className={styles.preview}>
      <p className={styles.lead}>{t("lead")}</p>
      <PlanTopics plan={plan} />
      <section className={styles.examples} aria-label={t("examples")}>
        <div className={styles.head}>
          <IconLabel icon="test" className={styles.title}>
            {t("examples")}
          </IconLabel>
          <Button
            size="compact"
            variant="secondary"
            icon="refresh"
            pending={preview.isFetching}
            pendingLabel={t("loading")}
            onClick={() => void preview.refetch()}
          >
            {t("another")}
          </Button>
        </div>
        <p className={styles.note}>{t("examplesLead")}</p>
        <Swap swapKey={preview.dataUpdatedAt} as="div" className={styles.list}>
          {examples.map((example, index) => (
            <ExampleCard key={example.topic.code} example={example} index={index} />
          ))}
        </Swap>
      </section>
    </div>
  )
}
