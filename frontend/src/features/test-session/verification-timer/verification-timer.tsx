import { useEffect, useState } from "react"
import { isInProgress, usePath } from "@/entities/candidate-path"
import type { CandidatePath } from "@/shared/api"
import { useFormatters, useTranslation } from "@/shared/i18n"
import { motionMs } from "@/shared/motion"
import { Banner, LoadError } from "@/shared/ui"

export interface VerificationTimerProps {
  readonly deadline: string
  readonly onFinished: (path: CandidatePath) => void
}

export function VerificationTimer({ deadline, onFinished }: VerificationTimerProps) {
  const { t } = useTranslation("test")
  const format = useFormatters()
  const path = usePath()
  const [now, setNow] = useState(Date.now)
  const remaining = Math.max(0, Math.ceil((Date.parse(deadline) - now) / 1000))
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), motionMs("--tick"))
    return () => window.clearInterval(timer)
  }, [])
  const { refetch } = path
  useEffect(() => {
    if (remaining === 0)
      void refetch().then(({ data }) => {
        if (data && !isInProgress(data)) onFinished(data)
      })
  }, [remaining, refetch, onFinished])
  return (
    <>
      <Banner
        tone="info"
        icon="clock"
        title={t("protection.remaining", { time: format.duration(remaining) })}
      >
        {t("protection.deadline", { date: format.dateTime(deadline) })}
      </Banner>
      {remaining === 0 && path.isError ? (
        <LoadError error={path.error} onRetry={() => void refetch()} pending={path.isFetching} />
      ) : null}
    </>
  )
}
