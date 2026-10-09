import { clsx } from "clsx"
import type { ReactNode } from "react"
import { Link } from "react-router"
import { staggerStyle } from "../../../motion"
import styles from "./list-row.module.css"

export interface ListRowProps {
  readonly to: string
  readonly title: ReactNode
  readonly leading?: ReactNode
  readonly meta?: ReactNode
  readonly trailing?: ReactNode
  readonly selected?: boolean
  readonly quiet?: boolean
  readonly motionIndex?: number | undefined
  readonly className?: string | undefined
}

export function ListRow({
  to,
  title,
  leading,
  meta,
  trailing,
  selected = false,
  quiet = false,
  motionIndex,
  className,
}: ListRowProps) {
  return (
    <li
      className={clsx(styles.item, motionIndex !== undefined && styles.entering)}
      style={motionIndex === undefined ? undefined : staggerStyle(motionIndex)}
    >
      <Link
        to={to}
        className={clsx(styles.row, className)}
        aria-current={selected ? "true" : undefined}
        data-selected={selected}
        data-quiet={quiet}
      >
        {leading === undefined ? null : <span className={styles.leading}>{leading}</span>}
        <span className={styles.body}>
          <span className={styles.title}>{title}</span>
          {meta === undefined ? null : <span className={styles.meta}>{meta}</span>}
        </span>
        {trailing === undefined ? null : <span className={styles.trailing}>{trailing}</span>}
      </Link>
    </li>
  )
}
