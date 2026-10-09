import type { CSSProperties } from "react"
import { useTranslation } from "@/shared/i18n"
import { ButtonLink, Lockup, Tooltip } from "@/shared/ui"
import styles from "./test-bar.module.css"

export interface TestBarProps {
  readonly title: string
  readonly number: number
  readonly max: number
  readonly block: boolean
  readonly exitTo: string
}

export function TestBar({ title, number, max, block, exitTo }: TestBarProps) {
  const { t } = useTranslation("test")
  const progress = Math.min(1, Math.max(0, (number - 1) / Math.max(1, max)))
  return (
    <header className={styles.bar} data-surface="inverse">
      <Lockup size="sm" className={styles.lockup} />
      <div className={styles.center}>
        <h1 className={styles.title} tabIndex={-1}>
          {title}
        </h1>
        <p className={styles.progress} aria-live="polite">
          {block ? t("progressBlock", { number, max }) : t("progress", { number, max })}
        </p>
      </div>
      <Tooltip content={t("exitHint")} side="bottom">
        <ButtonLink to={exitTo} variant="ghost" icon="arrow-left" className={styles.exit}>
          {t("exit")}
        </ButtonLink>
      </Tooltip>
      <span
        className={styles.track}
        style={{ "--test-progress": progress } as CSSProperties}
        aria-hidden="true"
      />
    </header>
  )
}
