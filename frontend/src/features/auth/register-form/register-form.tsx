import { useMutation } from "@tanstack/react-query"
import { useId, useState } from "react"
import { api, type Role, unwrap } from "@/shared/api"
import { useErrorText, useLocale, useTranslation } from "@/shared/i18n"
import { Banner, Button, Form, PasswordField, TextField } from "@/shared/ui"
import { ConsentField } from "../consent/consent-field"
import styles from "./register-form.module.css"

export interface RegisterFormProps {
  readonly role: Role
  readonly onSent: (email: string) => void
}

export function RegisterForm({ role, onSent }: RegisterFormProps) {
  const { t } = useTranslation("auth")
  const errorText = useErrorText()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [consent, setConsent] = useState(false)
  const { locale } = useLocale()
  const reasonId = useId()
  const register = useMutation({
    mutationFn: () =>
      unwrap(api.POST("/api/auth/register", { body: { email, password, role, locale } })),
    onSuccess: (user) => onSent(user.email),
  })

  const submit = () => {
    if (consent) register.mutate()
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
        hint={t("field.passwordHint")}
        autoComplete="new-password"
        required
        minLength={8}
        maxLength={128}
        value={password}
        onChange={setPassword}
        showText={t("field.showPassword")}
        hideText={t("field.hidePassword")}
      />
      <ConsentField role={role} checked={consent} onChange={setConsent} />
      {register.isError && <Banner tone="critical" title={errorText(register.error)} />}
      <div className={styles.submit}>
        <Button
          type="submit"
          fullWidth
          pending={register.isPending}
          pendingLabel={t("register.pending")}
          disabled={!consent}
          aria-describedby={consent ? undefined : reasonId}
        >
          {t("register.submit")}
        </Button>
        {consent ? null : (
          <p id={reasonId} className={styles.reason}>
            {t("register.needConsent")}
          </p>
        )}
      </div>
    </Form>
  )
}
