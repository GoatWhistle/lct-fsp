import { useMutation } from "@tanstack/react-query"
import { useEffect, useRef, useState } from "react"
import { useSearchParams } from "react-router"
import { ResendVerification } from "@/features/auth"
import { api, unwrap } from "@/shared/api"
import { useDocumentTitle, useErrorText, useTranslation } from "@/shared/i18n"
import { Banner, ButtonLink, IconLabel, Spinner, TextField } from "@/shared/ui"
import { AuthLayout } from "../public-chrome/auth-layout/auth-layout"
import { AuthHint } from "../public-chrome/auth-layout/auth-parts"

function FailedState({ message }: { readonly message: string }) {
  const { t } = useTranslation("auth")
  const [email, setEmail] = useState("")
  return (
    <>
      <Banner tone="critical" title={message} />
      <AuthHint>{t("verify.resendHint")}</AuthHint>
      <TextField
        label={t("field.email")}
        type="email"
        icon="mail"
        value={email}
        onChange={setEmail}
      />
      <ResendVerification email={email} />
    </>
  )
}

export function VerifyEmailPage() {
  const { t } = useTranslation("auth")
  const errorText = useErrorText()
  const [params] = useSearchParams()
  const token = params.get("token") ?? ""
  const sent = useRef(false)
  const verify = useMutation({
    mutationFn: () => unwrap(api.POST("/api/auth/verify-email", { body: { token } })),
  })

  useEffect(() => {
    if (token === "" || sent.current) return
    sent.current = true
    verify.mutate()
  }, [token, verify])

  const title =
    token === "" || verify.isError
      ? t("verify.failed")
      : verify.isSuccess
        ? t("verify.done")
        : t("verify.checking")
  useDocumentTitle(title)

  return (
    <AuthLayout title={title}>
      {token === "" && <FailedState message={t("verify.noToken")} />}
      {token !== "" && verify.isError && <FailedState message={errorText(verify.error)} />}
      {verify.isSuccess && (
        <>
          <IconLabel icon="accepted" tone="accent">
            {t("verify.doneText", { email: verify.data.email })}
          </IconLabel>
          <ButtonLink to={`/login?email=${encodeURIComponent(verify.data.email)}`} fullWidth>
            {t("verify.login")}
          </ButtonLink>
        </>
      )}
      {token !== "" && !verify.isError && !verify.isSuccess && (
        <IconLabel leading={<Spinner label={t("verify.checking")} size="sm" />}>
          {t("verify.checkingText")}
        </IconLabel>
      )}
    </AuthLayout>
  )
}
