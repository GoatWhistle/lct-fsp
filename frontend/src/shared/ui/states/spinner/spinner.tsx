import { clsx } from "clsx"
import { useReducedMotion } from "../../../motion"
import { Icon } from "../../primitives/icon/icon"
import styles from "./spinner.module.css"

export interface SpinnerProps {
  readonly label: string
  readonly size?: "sm" | "md" | undefined
  readonly delayed?: boolean | undefined
  readonly className?: string | undefined
}

export function Spinner({ label, size = "md", delayed = false, className }: SpinnerProps) {
  const reduced = useReducedMotion()
  return (
    <span
      className={clsx(styles.spinner, className)}
      role="status"
      data-reduced={reduced}
      data-delayed={delayed}
    >
      <Icon name="loader" size={size} className={styles.glyph} />
      <span className={reduced ? styles.label : "visually-hidden"}>{label}</span>
    </span>
  )
}
