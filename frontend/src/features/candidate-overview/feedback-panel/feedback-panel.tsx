import { useState } from "react"
import { useFeedback } from "@/entities/profile"
import type { FeedbackHint } from "@/shared/api"
import { useFormatters, useTranslation } from "@/shared/i18n"
import { Button, Dialog, IconLabel, LoadError, Skeleton, Stat } from "@/shared/ui"
import styles from "./feedback-panel.module.css"
import { HintRow } from "./hint-row"

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

function useHints(): readonly FeedbackHint[] {
  const feedback = useFeedback()
  return (feedback.data?.hints ?? []).filter((hint) => hint.action.kind !== "link_fsp")
}

function FeedbackContent() {
  const { t } = useTranslation("overview")
  const feedback = useFeedback()
  const hints = useHints()
  if (feedback.isError)
    return (
      <LoadError
        error={feedback.error}
        onRetry={() => void feedback.refetch()}
        pending={feedback.isFetching}
      />
    )
  if (feedback.data === undefined) return <Skeleton lines={4} />
  return (
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
  )
}

export function FeedbackButton() {
  const { t } = useTranslation("overview")
  const [open, setOpen] = useState(false)
  const hints = useHints()
  if (hints.length === 0) return null
  return (
    <>
      <Button variant="secondary" icon="match" onClick={() => setOpen(true)}>
        {t("feedback.open", { count: hints.length })}
      </Button>
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title={t("feedback.title")}
        description={t("feedback.lead")}
      >
        <FeedbackContent />
      </Dialog>
    </>
  )
}
