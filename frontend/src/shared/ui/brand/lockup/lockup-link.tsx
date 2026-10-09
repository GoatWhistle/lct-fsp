import { useTranslation } from "react-i18next"
import { Link } from "react-router"
import { FspMark } from "../fsp-mark/fsp-mark"
import { Lockup, type LockupSize } from "./lockup"
import styles from "./lockup.module.css"

export interface LockupLinkProps {
  readonly to: string
  readonly compact?: boolean
  readonly size?: LockupSize
}

export function LockupLink({ to, compact = false, size = "sm" }: LockupLinkProps) {
  const { t } = useTranslation()
  return (
    <Link to={to} className={styles.link} aria-label={t("app.byFsp")} viewTransition>
      {compact ? <FspMark className={styles.compactMark} /> : <Lockup size={size} />}
    </Link>
  )
}
