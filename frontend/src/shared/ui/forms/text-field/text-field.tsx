import { clsx } from "clsx"
import type { FocusEvent, ReactNode, Ref } from "react"
import { Icon, type IconName } from "../../primitives/icon/icon"
import { Field } from "../field/field"
import styles from "./text-field.module.css"

export type TextFieldType = "text" | "email" | "tel" | "url" | "search" | "password"

export interface TextFieldProps {
  readonly label: string
  readonly value: string
  readonly onChange: (value: string) => void
  readonly type?: TextFieldType
  readonly name?: string | undefined
  readonly autoComplete?: string | undefined
  readonly inputMode?: "text" | "email" | "tel" | "url" | "numeric" | "search" | undefined
  readonly placeholder?: string | undefined
  readonly maxLength?: number | undefined
  readonly minLength?: number | undefined
  readonly required?: boolean | undefined
  readonly hint?: string | undefined
  readonly error?: string | undefined
  readonly disabled?: boolean | undefined
  readonly hideLabel?: boolean | undefined
  readonly icon?: IconName | undefined
  readonly trailing?: ReactNode
  readonly onBlur?: ((event: FocusEvent<HTMLInputElement>) => void) | undefined
  readonly inputRef?: Ref<HTMLInputElement> | undefined
  readonly className?: string | undefined
}

export function TextField({
  label,
  value,
  onChange,
  type = "text",
  name,
  autoComplete,
  inputMode,
  placeholder,
  maxLength,
  minLength,
  required,
  hint,
  error,
  disabled,
  hideLabel,
  icon,
  trailing,
  onBlur,
  inputRef,
  className,
}: TextFieldProps) {
  return (
    <Field
      label={label}
      hint={hint}
      error={error}
      hideLabel={hideLabel}
      required={required}
      className={className}
    >
      {(control) => (
        <span
          className={styles.wrap}
          data-icon={icon !== undefined}
          data-trailing={trailing !== undefined}
        >
          {icon === undefined ? null : <Icon name={icon} size="sm" className={styles.icon} />}
          <input
            {...control}
            ref={inputRef}
            className={clsx(styles.input)}
            type={type}
            name={name}
            autoComplete={autoComplete}
            inputMode={inputMode}
            value={value}
            placeholder={placeholder}
            maxLength={maxLength}
            minLength={minLength}
            required={required}
            disabled={disabled}
            onBlur={onBlur}
            onChange={(event) => onChange(event.target.value)}
          />
          {trailing === undefined ? null : <span className={styles.trailing}>{trailing}</span>}
        </span>
      )}
    </Field>
  )
}
