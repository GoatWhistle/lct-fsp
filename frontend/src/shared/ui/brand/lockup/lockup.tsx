import { clsx } from "clsx"
import { useTranslation } from "react-i18next"
import { FspMark } from "../fsp-mark/fsp-mark"
import styles from "./lockup.module.css"

export type LockupSize = "sm" | "md" | "lg"

export interface LockupProps {
  readonly size?: LockupSize
  readonly withMark?: boolean
  readonly className?: string | undefined
}

const SIZE_CLASS: Readonly<Record<LockupSize, string | undefined>> = {
  sm: styles.small,
  md: undefined,
  lg: styles.large,
}

const WORD = "calibr"

export function Lockup({ size = "md", withMark = true, className }: LockupProps) {
  const { t } = useTranslation()
  return (
    <span
      className={clsx(styles.lockup, SIZE_CLASS[size], className)}
      role="img"
      aria-label={t("app.byFsp")}
    >
      {withMark && <FspMark className={styles.mark} />}
      <span className={styles.word} aria-hidden="true">
        {WORD}
      </span>
    </span>
  )
}
