import { clsx } from "clsx"
import { type ReactNode, useId } from "react"
import { useInputModality } from "../../../motion"
import styles from "./radio-group.module.css"

export interface RadioOption<T extends string> {
  readonly value: T
  readonly label: ReactNode
  readonly hint?: string | undefined
  readonly disabled?: boolean | undefined
  readonly shortcut?: string | undefined
}

export interface RadioGroupProps<T extends string> {
  readonly label: string
  readonly value: T | null
  readonly options: readonly RadioOption<T>[]
  readonly onChange: (value: T) => void
  readonly orientation?: "vertical" | "horizontal" | undefined
  readonly appearance?: "plain" | "card" | undefined
  readonly hideLabel?: boolean | undefined
  readonly disabled?: boolean | undefined
  readonly className?: string | undefined
}

export function RadioGroup<T extends string>({
  label,
  value,
  options,
  onChange,
  orientation = "vertical",
  appearance = "plain",
  hideLabel = false,
  disabled = false,
  className,
}: RadioGroupProps<T>) {
  const name = useId()
  const modality = useInputModality()
  return (
    <fieldset
      className={clsx(styles.group, className)}
      data-orientation={orientation}
      data-appearance={appearance}
      data-instant={modality.instant}
      disabled={disabled}
      onKeyDown={modality.onKeyDown}
      onPointerDown={modality.onPointerDown}
    >
      <legend className={hideLabel ? "visually-hidden" : styles.legend}>{label}</legend>
      {options.map((option) => {
        const checked = option.value === value
        const optionDisabled = disabled || option.disabled === true
        return (
          <label
            key={option.value}
            className={clsx(styles.option, appearance === "card" && styles.cardOption)}
            data-checked={checked}
            data-disabled={optionDisabled}
          >
            <input
              className={styles.input}
              type="radio"
              name={name}
              value={option.value}
              checked={checked}
              disabled={optionDisabled}
              onChange={() => onChange(option.value)}
            />
            <span className={styles.ring} aria-hidden="true">
              <span className={styles.dot} data-on={checked} data-motion="fade" />
            </span>
            {option.shortcut === undefined ? null : (
              <kbd className={styles.shortcut}>{option.shortcut}</kbd>
            )}
            <span className={styles.text}>
              <span>{option.label}</span>
              {option.hint === undefined ? null : (
                <span className={styles.hint}>{option.hint}</span>
              )}
            </span>
          </label>
        )
      })}
    </fieldset>
  )
}
