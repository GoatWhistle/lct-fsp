import { useEffect, useRef } from "react"
import { useSearchParams } from "react-router"
import { COMPANY_DIALOG_LINK, useConfirmDomain } from "@/entities/company"
import { useDocumentTitle, useErrorText, useTranslation } from "@/shared/i18n"
import { Banner, ButtonLink, IconLabel, Spinner } from "@/shared/ui"
import { AuthLayout } from "../public-chrome/auth-layout/auth-layout"

export function VerifyDomainPage() {
  const { t } = useTranslation("company")
  const errorText = useErrorText()
  const [params] = useSearchParams()
  const token = params.get("token") ?? ""
  const sent = useRef(false)
  const confirm = useConfirmDomain()

  useEffect(() => {
    if (token === "" || sent.current) return
    sent.current = true
    confirm.mutate(token)
  }, [token, confirm])

  const failed = token === "" || confirm.isError
  const title = failed
    ? t("domain.confirmFailed")
    : confirm.isSuccess
      ? t("domain.confirmDone")
      : t("domain.confirmChecking")
  useDocumentTitle(title)

  return (
    <AuthLayout title={title}>
      {token === "" ? <Banner tone="critical" title={t("domain.noToken")} /> : null}
      {confirm.isError ? <Banner tone="critical" title={errorText(confirm.error)} /> : null}
      {confirm.isSuccess ? (
        <>
          <IconLabel icon="accepted" tone="accent">
            {t("domain.verified", { domain: confirm.data.verified_domain ?? "" })}
          </IconLabel>
          <ButtonLink to={`/employer${COMPANY_DIALOG_LINK}`} fullWidth>
            {t("domain.toCompany")}
          </ButtonLink>
        </>
      ) : null}
      {!failed && !confirm.isSuccess ? (
        <IconLabel leading={<Spinner label={t("domain.confirmChecking")} size="sm" />}>
          {t("domain.confirmChecking")}
        </IconLabel>
      ) : null}
    </AuthLayout>
  )
}
