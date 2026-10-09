import { useEffect } from "react"
import { useBlocker } from "react-router"
import { useTranslation } from "@/shared/i18n"
import { ConfirmDialog } from "@/shared/ui"

export interface LeaveGuardProps {
  readonly when: boolean
}

export function LeaveGuard({ when }: LeaveGuardProps) {
  const { t } = useTranslation()
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      when && currentLocation.pathname !== nextLocation.pathname,
  )

  useEffect(() => {
    if (!when) return
    const onBeforeUnload = (event: BeforeUnloadEvent) => event.preventDefault()
    window.addEventListener("beforeunload", onBeforeUnload)
    return () => window.removeEventListener("beforeunload", onBeforeUnload)
  }, [when])

  return (
    <ConfirmDialog
      open={blocker.state === "blocked"}
      tone="danger"
      title={t("leave.title")}
      description={t("leave.text")}
      confirmLabel={t("leave.leave")}
      cancelLabel={t("leave.stay")}
      onConfirm={() => blocker.proceed?.()}
      onClose={() => blocker.reset?.()}
    />
  )
}
