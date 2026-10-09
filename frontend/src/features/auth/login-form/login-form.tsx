import { useMutation } from "@tanstack/react-query"
import { useState } from "react"
import { useNavigate } from "react-router"
import { CABINET_PATH, useSetSession } from "@/entities/session"
import { api, isApiError, unwrap } from "@/shared/api"
import { useErrorText, useTranslation } from "@/shared/i18n"
import { Banner, Button, Form, PasswordField, TextField } from "@/shared/ui"
import { ResendVerification } from "../resend-verification/resend-verification"

export interface LoginFormProps {
  readonly initialEmail?: string
  readonly next?: string | null
}

function safeNext(next: string | null | undefined): string | null {
  if (next === null || next === undefined) return null
  return next.startsWith("/") && next.charAt(1) !== "/" ? next : null
}

export function LoginForm({ initialEmail = "", next }: LoginFormProps) {
  const { t } = useTranslation("auth")
  const errorText = useErrorText()
  const setSession = useSetSession()
  const navigate = useNavigate()
  const [email, setEmail] = useState(initialEmail)
  const [password, setPassword] = useState("")
  const login = useMutation({
    mutationFn: () => unwrap(api.POST("/api/auth/login", { body: { email, password } })),
    onSuccess: (user) => {
      setSession(user)
      navigate(safeNext(next) ?? CABINET_PATH[user.role], { replace: true, viewTransition: true })
    },
  })
  const unverified = isApiError(login.error, "email_not_verified")

  const submit = () => {
    login.mutate()
  }

  return (
    <Form onSubmit={submit}>
      <TextField
        label={t("field.email")}
        type="email"
        icon="mail"
        autoComplete="email"
        required
        value={email}
        onChange={setEmail}
      />
      <PasswordField
        label={t("field.password")}
        autoComplete="current-password"
        required
        value={password}
        onChange={setPassword}
        showText={t("field.showPassword")}
        hideText={t("field.hidePassword")}
      />
      {login.isError && <Banner tone="critical" title={errorText(login.error)} />}
      {unverified && <ResendVerification email={email} />}
      <Button type="submit" fullWidth pending={login.isPending} pendingLabel={t("login.pending")}>
        {t("login.submit")}
      </Button>
    </Form>
  )
}
