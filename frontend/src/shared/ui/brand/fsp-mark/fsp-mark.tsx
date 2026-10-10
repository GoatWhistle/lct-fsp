import { clsx } from "clsx"
import type { SVGProps } from "react"
import styles from "./fsp-mark.module.css"
import { FSP_MARK_BLUE, FSP_MARK_NEUTRAL, FSP_MARK_RED, FSP_MARK_VIEWBOX } from "./fsp-mark-paths"

export type FspMarkTone = "brand" | "mono"

export interface FspMarkProps {
  readonly tone?: FspMarkTone
  readonly label?: string | undefined
  readonly className?: string | undefined
}

export function FspMark({ tone = "brand", label, className }: FspMarkProps) {
  return (
    <svg
      className={clsx(styles.mark, tone === "mono" && styles.mono, className)}
      viewBox={FSP_MARK_VIEWBOX}
      role={label === undefined ? undefined : "img"}
      aria-label={label}
      aria-hidden={label === undefined ? true : undefined}
    >
      <path className={styles.neutral} d={FSP_MARK_NEUTRAL} />
      <path className={styles.red} d={FSP_MARK_RED} />
      <path className={styles.blue} d={FSP_MARK_BLUE} />
    </svg>
  )
}

export function FspGlyph(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox={FSP_MARK_VIEWBOX} aria-hidden="true" {...props}>
      <path className={styles.neutral} d={FSP_MARK_NEUTRAL} />
      <path className={styles.red} d={FSP_MARK_RED} />
      <path className={styles.blue} d={FSP_MARK_BLUE} />
    </svg>
  )
}
