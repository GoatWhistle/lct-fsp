import { clsx } from "clsx"
import type { ReactNode } from "react"
import { Icon, type IconName, type IconSize } from "../icon/icon"
import styles from "./icon-label.module.css"

export interface IconLabelProps {
  readonly icon?: IconName | undefined
  readonly leading?: ReactNode
  readonly size?: IconSize
  readonly tone?: "default" | "secondary" | "accent" | "danger"
  readonly className?: string | undefined
  readonly children: ReactNode
}

export function IconLabel({
  icon,
  leading,
  size = "sm",
  tone = "default",
  className,
  children,
}: IconLabelProps) {
  return (
    <span className={clsx(styles.label, className)} data-tone={tone}>
      {icon === undefined && leading === undefined ? null : (
        <span className={styles.glyph}>
          {icon === undefined ? leading : <Icon name={icon} size={size} />}
        </span>
      )}
      <span className={styles.text}>{children}</span>
    </span>
  )
}
