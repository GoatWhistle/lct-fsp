import { clsx } from "clsx"
import type { ReactNode } from "react"
import styles from "./flag-row.module.css"

export interface FlagRowProps {
  readonly mark: ReactNode
  readonly title: ReactNode
  readonly note: ReactNode
  readonly trailing?: ReactNode
  readonly active: boolean
  readonly className?: string | undefined
}

export function FlagRow({ mark, title, note, trailing, active, className }: FlagRowProps) {
  return (
    <div className={clsx(styles.flag, className)} data-active={active}>
      <span className={styles.mark}>{mark}</span>
      <span className={styles.text}>
        <span className={styles.title}>{title}</span>
        <span className={styles.note}>{note}</span>
      </span>
      {trailing}
    </div>
  )
}

export interface FlagListProps {
  readonly children: ReactNode
  readonly layout?: "grid" | "rows"
  readonly className?: string | undefined
}

export function FlagList({ children, layout = "grid", className }: FlagListProps) {
  return (
    <div className={clsx(styles.list, className)} data-layout={layout}>
      {children}
    </div>
  )
}
