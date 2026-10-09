import { useFeedback } from "@/entities/profile"
import { useFormatters, useTranslation } from "@/shared/i18n"
import { Card, IconLabel, LoadError, Skeleton, Stat } from "@/shared/ui"
import styles from "./feedback-panel.module.css"
import { HintRow } from "./hint-row"

export interface FeedbackPanelProps {
  readonly motionIndex?: number
  readonly withoutFspLink?: boolean
  readonly className?: string | undefined
}

function Placement() {
  const { t } = useTranslation("overview")
  const format = useFormatters()
  const feedback = useFeedback()
  const data = feedback.data
  if (data === undefined) return null
  if (data.placement === null)
    return (
      <IconLabel icon="info" tone="secondary" className={styles.few}>
        {t("feedback.few", { days: data.period_days })}
      </IconLabel>
    )
  return (
    <div className={styles.stats}>
      <Stat
        icon="need"
        label={t("feedback.selections", { days: data.period_days })}
        value={format.integer(data.placement.selections)}
      />
      <Stat
        icon="sort"
        label={t("feedback.median")}
        value={format.number(data.placement.median_position)}
      />
      <Stat
        icon="match"
        label={t("feedback.exact")}
        value={format.percent(data.placement.exact_share)}
      />
    </div>
  )
}

export function FeedbackPanel({
  motionIndex,
  withoutFspLink = false,
  className,
}: FeedbackPanelProps) {
  const { t } = useTranslation("overview")
  const feedback = useFeedback()
  const hints = (feedback.data?.hints ?? []).filter(
    (hint) => !withoutFspLink || hint.action.kind !== "link_fsp",
  )
  return (
    <Card
      title={t("feedback.title")}
      description={t("feedback.lead")}
      motionIndex={motionIndex}
      className={className}
    >
      {feedback.isError ? (
        <LoadError
          error={feedback.error}
          onRetry={() => void feedback.refetch()}
          pending={feedback.isFetching}
        />
      ) : feedback.data === undefined ? (
        <Skeleton lines={4} />
      ) : (
        <>
          <Placement />
          {hints.length === 0 ? null : (
            <ul className={styles.hints} aria-label={t("feedback.hints")}>
              {hints.map((hint, index) => (
                <HintRow key={hint.topic?.code ?? hint.action.kind} hint={hint} index={index} />
              ))}
            </ul>
          )}
        </>
      )}
    </Card>
  )
}
