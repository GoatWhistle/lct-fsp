import { useSearchParams } from "react-router"
import { useTranslation } from "@/shared/i18n"
import { Banner } from "@/shared/ui"

const LINKED = "linked"
const KNOWN_ERRORS = new Set([
  "fsp_id_unavailable",
  "fsp_id_rejected",
  "fsp_authorization_invalid",
  "fsp_email_unverified",
  "fsp_email_taken",
  "fsp_id_taken",
  "fsp_already_linked",
  "not_authenticated",
  "wrong_role",
])

export function FspReturn() {
  const { t } = useTranslation(["profile", "errors"])
  const [params, setParams] = useSearchParams()
  const linked = params.get("fsp") === LINKED
  const error = params.get("fsp_error")
  const dismiss = () =>
    setParams(
      (current) => {
        const next = new URLSearchParams(current)
        next.delete("fsp")
        next.delete("fsp_error")
        return next
      },
      { replace: true },
    )
  if (error !== null) {
    const code = KNOWN_ERRORS.has(error) ? error : "unknown"
    return (
      <Banner tone="critical" icon="fsp" title={t("profile:fsp.returnError")} onDismiss={dismiss}>
        {t(`errors:fsp.${code}` as never)}
      </Banner>
    )
  }
  return (
    <Banner
      tone="info"
      icon="fsp"
      open={linked}
      title={t("profile:fsp.returnLinked")}
      onDismiss={dismiss}
    >
      {t("profile:fsp.returnLinkedText")}
    </Banner>
  )
}
