import { clsx } from "clsx"
import type { ReactNode } from "react"
import { useTranslation } from "react-i18next"
import { Icon, type IconName } from "../../primitives/icon/icon"
import styles from "./chip.module.css"

export type ChipTone = "neutral" | "accent"

export interface ChipProps {
  readonly icon?: IconName | undefined
  readonly tone?: ChipTone
  readonly removeLabel?: string | undefined
  readonly onRemove?: (() => void) | undefined
  readonly className?: string | undefined
  readonly children: ReactNode
}

export function Chip({
  icon,
  tone = "neutral",
  removeLabel,
  onRemove,
  className,
  children,
}: ChipProps) {
  const { t } = useTranslation()
  return (
    <span className={clsx(styles.chip, className)} data-tone={tone}>
      {icon === undefined ? null : <Icon name={icon} size="sm" />}
      <span className={styles.label}>{children}</span>
      {onRemove === undefined ? null : (
        <button
          type="button"
          className={styles.remove}
          aria-label={removeLabel ?? t("combobox.remove", { label: String(children) })}
          onClick={onRemove}
        >
          <Icon name="close" size="sm" />
        </button>
      )}
    </span>
  )
}
