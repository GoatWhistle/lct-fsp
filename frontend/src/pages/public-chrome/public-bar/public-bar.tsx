import { clsx } from "clsx"
import { LocaleSwitch, ThemeSwitch } from "@/features/preferences"
import { useTranslation } from "@/shared/i18n"
import { ButtonLink, LockupLink } from "@/shared/ui"
import styles from "./public-bar.module.css"

export interface PublicBarProps {
  readonly showLogin?: boolean
  readonly className?: string | undefined
}

export function PublicBar({ showLogin = true, className }: PublicBarProps) {
  const { t } = useTranslation()
  return (
    <header className={clsx(styles.bar, className)}>
      <LockupLink to="/" />
      <div className={styles.tools}>
        <LocaleSwitch />
        <ThemeSwitch />
        {showLogin && (
          <ButtonLink to="/login" variant="secondary" size="compact" className={styles.login}>
            {t("action.signIn")}
          </ButtonLink>
        )}
      </div>
    </header>
  )
}
