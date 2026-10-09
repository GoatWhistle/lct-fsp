import { useErrorText, useTranslation } from "@/shared/i18n"
import { Button, FspMark, toast } from "@/shared/ui"
import styles from "./fsp-sign-in.module.css"
import { type FspIntent, useFspAuthorize } from "./use-fsp-authorize"

export interface FspSignInProps {
  readonly intent?: FspIntent
  readonly label?: string | undefined
  readonly variant?: "primary" | "secondary" | "dark"
  readonly fullWidth?: boolean
}

export function FspSignIn({
  intent = "login",
  label,
  variant = "secondary",
  fullWidth = false,
}: FspSignInProps) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const authorize = useFspAuthorize()
  return (
    <Button
      variant={variant}
      fullWidth={fullWidth}
      pending={authorize.isPending}
      onClick={() =>
        authorize.mutate(intent, { onError: (error) => toast.error(errorText(error)) })
      }
    >
      <span className={styles.content}>
        <FspMark className={styles.mark} />
        {label ?? t("brand.signInFsp")}
      </span>
    </Button>
  )
}
