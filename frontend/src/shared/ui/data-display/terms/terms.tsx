import { clsx } from "clsx"
import type { ReactNode } from "react"
import { Icon, type IconName } from "../../primitives/icon/icon"
import styles from "./terms.module.css"

export interface TermItem {
  readonly key: string
  readonly label: string
  readonly icon: IconName
  readonly value: ReactNode
  readonly tone?: "default" | "danger" | undefined
  readonly prose?: boolean | undefined
}

export interface TermsProps {
  readonly items: readonly TermItem[]
  readonly className?: string | undefined
}

export function Terms({ items, className }: TermsProps) {
  return (
    <dl className={clsx(styles.terms, className)}>
      {items.map((item) => (
        <div
          key={item.key}
          className={styles.term}
          data-tone={item.tone ?? "default"}
          data-prose={item.prose === true}
        >
          <dt className={styles.label}>
            <Icon name={item.icon} size="sm" className={styles.icon} />
            {item.label}
          </dt>
          <dd className={styles.value}>{item.value}</dd>
        </div>
      ))}
    </dl>
  )
}
