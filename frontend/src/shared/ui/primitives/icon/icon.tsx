import { clsx } from "clsx"
import styles from "./icon.module.css"
import { ICONS, type IconName } from "./icons"

export type IconSize = "sm" | "md" | "lg" | "xl"

export interface IconProps {
  readonly name: IconName
  readonly size?: IconSize
  readonly label?: string
  readonly className?: string | undefined
}

const SIZE_CLASS: Readonly<Record<IconSize, string | undefined>> = {
  sm: styles.sm,
  md: styles.md,
  lg: styles.lg,
  xl: styles.xl,
}

export function Icon({ name, size = "md", label, className }: IconProps) {
  const Glyph = ICONS[name]
  const labelled = label !== undefined && label !== ""
  return (
    <Glyph
      className={clsx(styles.icon, SIZE_CLASS[size], className)}
      data-icon={name}
      focusable="false"
      aria-hidden={labelled ? undefined : true}
      aria-label={labelled ? label : undefined}
      role={labelled ? "img" : undefined}
    />
  )
}

export type { IconName } from "./icons"
