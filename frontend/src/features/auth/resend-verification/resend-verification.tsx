import { useMutation } from "@tanstack/react-query"
import { useEffect, useState } from "react"
import { api, unwrap } from "@/shared/api"
import { useLocale, useTranslation } from "@/shared/i18n"
import { motionMs } from "@/shared/motion"
import { Button, IconLabel } from "@/shared/ui"
import styles from "./resend-verification.module.css"

export interface ResendVerificationProps {
  readonly email: string
}

export function ResendVerification({ email }: ResendVerificationProps) {
  const { t } = useTranslation("auth")
  const [until, setUntil] = useState(0)
  const [now, setNow] = useState(() => Date.now())
  const { locale } = useLocale()
  const resend = useMutation({
    mutationFn: () =>
      unwrap(api.POST("/api/auth/resend-verification", { body: { email, locale } })),
    onSettled: () => setUntil(Date.now() + motionMs("--resend-cooldown")),
  })
  const left = Math.max(0, Math.ceil((until - now) / motionMs("--tick")))

  useEffect(() => {
    if (until <= Date.now()) return
    const timer = window.setInterval(() => setNow(Date.now()), motionMs("--tick"))
    return () => window.clearInterval(timer)
  }, [until])

  return (
    <div className={styles.resend}>
      <Button
        variant="secondary"
        icon="mail"
        pending={resend.isPending}
        pendingLabel={t("resend.pending")}
        disabled={email === "" || left > 0}
        onClick={() => resend.mutate()}
      >
        {left > 0 ? t("resend.cooldown", { seconds: left }) : t("resend.action")}
      </Button>
      {resend.isSuccess && (
        <IconLabel icon="accepted" tone="accent">
          {t("resend.done")}
        </IconLabel>
      )}
    </div>
  )
}
