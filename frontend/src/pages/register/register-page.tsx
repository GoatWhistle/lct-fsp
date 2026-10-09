import { useState } from "react"
import { useSearchParams } from "react-router"
import { FspTile, RegisterForm, ResendVerification } from "@/features/auth"
import { JuryActions } from "@/features/jury-mode"
import type { Role } from "@/shared/api"
import { useDocumentTitle, useTranslation } from "@/shared/i18n"
import { withViewTransition } from "@/shared/motion"
import { ChoiceTiles } from "@/shared/ui"
import { AuthLayout } from "../public-chrome/auth-layout/auth-layout"
import {
  AuthDivider,
  AuthGroup,
  AuthHint,
  AuthSwitch,
} from "../public-chrome/auth-layout/auth-parts"
import styles from "./register-page.module.css"

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
      <div className={styles.role}>
        <ChoiceTiles
          legend={t("register.role")}
          hideLegend
          layout="inline"
          columns="compact"
          value={role}
          onChange={(next) => void withViewTransition("layout", () => setRole(next))}
          tiles={[
            {
              value: "candidate",
              title: t("register.candidate"),
              icon: "profile",
            },
            {
              value: "employer",
              title: t("register.employer"),
              icon: "company",
            },
          ]}
        />
      </div>
      {role === "candidate" ? (
        <div className={styles.fsp}>
          <AuthGroup>
            <FspTile hint={t("register.fspFirst")} />
            <AuthDivider>{t("login.or")}</AuthDivider>
          </AuthGroup>
        </div>
      ) : null}
      <div className={styles.form}>
        <RegisterForm role={role} onSent={setSentTo} />
      </div>
      <div className={styles.jury}>
        <JuryActions />
      </div>
      <div className={styles.switch}>
        <AuthSwitch text={t("register.haveAccount")} to="/login" link={t("register.login")} />
      </div>
    </AuthLayout>
  )
}
