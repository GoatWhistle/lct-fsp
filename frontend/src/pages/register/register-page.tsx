import { useState } from "react"
import { useSearchParams } from "react-router"
import { FspSignIn, RegisterForm, ResendVerification } from "@/features/auth"
import type { Role } from "@/shared/api"
import { useDocumentTitle, useTranslation } from "@/shared/i18n"
import { Swap } from "@/shared/motion"
import { Segmented } from "@/shared/ui"
import { AuthLayout } from "../public-chrome/auth-layout/auth-layout"
import {
  AuthBlock,
  AuthDivider,
  AuthGroup,
  AuthHint,
  AuthSwitch,
} from "../public-chrome/auth-layout/auth-parts"

export function RegisterPage() {
  const { t } = useTranslation("auth")
  const [params] = useSearchParams()
  const [role, setRole] = useState<Role>(
    params.get("role") === "employer" ? "employer" : "candidate",
  )
  const [sentTo, setSentTo] = useState<string | null>(null)
  useDocumentTitle(sentTo === null ? t("register.title") : t("sent.title"))

  if (sentTo !== null) {
    return (
      <AuthLayout title={t("sent.title")}>
        <AuthHint>{t("sent.text", { email: sentTo })}</AuthHint>
        <ResendVerification email={sentTo} />
      </AuthLayout>
    )
  }

  return (
    <AuthLayout title={t("register.title")}>
      <Segmented
        label={t("register.role")}
        value={role}
        onChange={setRole}
        options={[
          { value: "candidate", label: t("register.candidate"), icon: "profile" },
          { value: "employer", label: t("register.employer"), icon: "company" },
        ]}
      />
      <Swap swapKey={role} as="div">
        {role === "candidate" ? (
          <AuthGroup>
            <AuthBlock>
              <FspSignIn variant="primary" fullWidth />
              <AuthHint>{t("register.fspFirst")}</AuthHint>
            </AuthBlock>
            <AuthDivider>{t("login.or")}</AuthDivider>
          </AuthGroup>
        ) : null}
      </Swap>
      <RegisterForm role={role} onSent={setSentTo} />
      <AuthSwitch text={t("register.haveAccount")} to="/login" link={t("register.login")} />
    </AuthLayout>
  )
}
