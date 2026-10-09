import { CABINET_PATH } from "@/entities/session"
import { AccountMenu } from "@/features/auth"
import { LocaleSwitch, ThemeSwitch } from "@/features/preferences"
import type { User } from "@/shared/api"
import { LockupLink } from "@/shared/ui"
import styles from "./mobile-bar.module.css"

export interface MobileBarProps {
  readonly user: User
}

export function MobileBar({ user }: MobileBarProps) {
  return (
    <header className={styles.bar} data-surface="inverse">
      <LockupLink to={CABINET_PATH[user.role]} />
      <div className={styles.tools}>
        <LocaleSwitch />
        <ThemeSwitch />
        <AccountMenu user={user} placement="bottom-end" iconOnly />
      </div>
    </header>
  )
}
