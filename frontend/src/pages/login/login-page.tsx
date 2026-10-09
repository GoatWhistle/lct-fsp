import { useSearchParams } from "react-router"
import { FspSignIn, LoginForm } from "@/features/auth"
import { useDocumentTitle, useTranslation } from "@/shared/i18n"
import { Banner } from "@/shared/ui"
import { AuthLayout } from "../public-chrome/auth-layout/auth-layout"
import {
  AuthBlock,
  AuthDivider,
  AuthHint,
  AuthSwitch,
} from "../public-chrome/auth-layout/auth-parts"

const FSP_ERRORS = new Set([
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

export function LoginPage() {
  const { t } = useTranslation(["auth", "errors"])
  const [params] = useSearchParams()
  useDocumentTitle(t("login.title"))
  const fspError = params.get("fsp_error")
  const fspCode = fspError !== null && FSP_ERRORS.has(fspError) ? fspError : "unknown"
  return (
    <AuthLayout title={t("login.title")}>
      {fspError !== null && <Banner tone="critical" title={t(`errors:fsp.${fspCode}` as never)} />}
      <AuthBlock>
        <FspSignIn variant="primary" fullWidth />
        <AuthHint>{t("login.fspHint")}</AuthHint>
      </AuthBlock>
      <AuthDivider>{t("login.or")}</AuthDivider>
      <LoginForm initialEmail={params.get("email") ?? ""} next={params.get("next")} />
      <AuthSwitch text={t("login.noAccount")} to="/register" link={t("login.register")} />
    </AuthLayout>
  )
}
