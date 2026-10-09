import { clsx } from "clsx"
import type { ReactNode } from "react"
import { Link, type LinkProps } from "react-router"
import { Icon, type IconName } from "../icon/icon"
import { type ButtonSize, type ButtonVariant, SIZE_CLASS, VARIANT_CLASS } from "./button"
import styles from "./button.module.css"

export interface ButtonLinkProps extends Omit<LinkProps, "className" | "children"> {
  readonly variant?: ButtonVariant
  readonly size?: ButtonSize
  readonly icon?: IconName | undefined
  readonly iconPosition?: "start" | "end"
  readonly fullWidth?: boolean
  readonly className?: string | undefined
  readonly children: ReactNode
}

export function ButtonLink({
  variant = "primary",
  size = "regular",
  icon,
  iconPosition = "start",
  fullWidth = false,
  className,
  children,
  ...rest
}: ButtonLinkProps) {
  const glyph =
    icon === undefined ? null : <Icon name={icon} size={size === "icon" ? "md" : "sm"} />
  return (
    <Link
      viewTransition
      {...rest}
      className={clsx(
        styles.button,
        styles.link,
        VARIANT_CLASS[variant],
        SIZE_CLASS[size],
        fullWidth && styles.full,
        className,
      )}
    >
      {iconPosition === "start" && glyph}
      <span className={size === "icon" ? "visually-hidden" : styles.label}>{children}</span>
      {iconPosition === "end" && glyph}
    </Link>
  )
}
