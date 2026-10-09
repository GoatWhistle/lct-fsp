import { clsx } from "clsx"
import type { ButtonHTMLAttributes, MouseEvent, ReactNode, Ref } from "react"
import { Tooltip } from "../../overlays/tooltip/tooltip"
import { Icon, type IconName } from "../icon/icon"
import styles from "./button.module.css"

export type ButtonVariant = "primary" | "secondary" | "dark" | "ghost" | "danger" | "link"
export type ButtonSize = "regular" | "compact" | "icon"
export type ButtonShape = "default" | "pill"

export interface ButtonProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children" | "type"> {
  readonly variant?: ButtonVariant
  readonly size?: ButtonSize
  readonly shape?: ButtonShape
  readonly icon?: IconName
  readonly iconPosition?: "start" | "end"
  readonly pending?: boolean
  readonly pendingLabel?: string | undefined
  readonly fullWidth?: boolean
  readonly disabledReason?: string | undefined
  readonly type?: "button" | "submit"
  readonly ref?: Ref<HTMLButtonElement> | undefined
  readonly children: ReactNode
}

export const VARIANT_CLASS: Readonly<Record<ButtonVariant, string | undefined>> = {
  primary: styles.primary,
  secondary: styles.secondary,
  dark: styles.dark,
  danger: styles.danger,
  ghost: styles.ghost,
  link: styles.textLink,
}

export const SIZE_CLASS: Readonly<Record<ButtonSize, string | undefined>> = {
  regular: undefined,
  compact: styles.compact,
  icon: styles.iconOnly,
}

interface ButtonGlyphProps {
  readonly pending: boolean
  readonly icon: IconName | undefined
  readonly size: ButtonSize
}

function ButtonGlyph({ pending, icon, size }: ButtonGlyphProps) {
  const glyphSize = size === "icon" ? "md" : "sm"
  if (pending) return <Icon name="loader" size={glyphSize} className={styles.spinner} />
  return icon === undefined ? null : <Icon name={icon} size={glyphSize} />
}

interface ButtonLabelProps {
  readonly size: ButtonSize
  readonly pending: boolean
  readonly pendingLabel: string | undefined
  readonly children: ReactNode
}

function ButtonLabel({ size, pending, pendingLabel, children }: ButtonLabelProps) {
  if (size === "icon") return <span className="visually-hidden">{children}</span>
  return (
    <span className={styles.label} data-pending={pending && pendingLabel !== undefined}>
      <span className={styles.labelText}>{children}</span>
      {pendingLabel === undefined ? null : (
        <span className={styles.labelPending} aria-hidden={!pending}>
          {pendingLabel}
        </span>
      )}
    </span>
  )
}

export function Button({
  variant = "primary",
  size = "regular",
  shape = "default",
  icon,
  iconPosition = "start",
  pending = false,
  pendingLabel,
  fullWidth = false,
  disabledReason,
  disabled = false,
  type = "button",
  className,
  onClick,
  children,
  ...rest
}: ButtonProps) {
  const explained = disabled && disabledReason !== undefined
  const glyph = <ButtonGlyph pending={pending} icon={icon} size={size} />
  const handleClick = (event: MouseEvent<HTMLButtonElement>) => {
    if (pending || explained) {
      event.preventDefault()
      return
    }
    onClick?.(event)
  }

  const button = (
    <button
      {...rest}
      type={type}
      disabled={disabled && !explained}
      className={clsx(
        styles.button,
        VARIANT_CLASS[variant],
        SIZE_CLASS[size],
        shape === "pill" && styles.pill,
        fullWidth && styles.full,
        className,
      )}
      aria-busy={pending || undefined}
      aria-disabled={pending || explained || undefined}
      data-disabled={explained || undefined}
      data-variant={variant}
      onClick={handleClick}
    >
      {iconPosition === "start" && glyph}
      <ButtonLabel size={size} pending={pending} pendingLabel={pendingLabel}>
        {children}
      </ButtonLabel>
      {iconPosition === "end" && glyph}
    </button>
  )
  return explained ? <Tooltip content={disabledReason}>{button}</Tooltip> : button
}
