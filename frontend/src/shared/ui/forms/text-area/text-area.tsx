import { type KeyboardEvent, useLayoutEffect, useRef } from "react"
import { Field } from "../field/field"
import styles from "./text-area.module.css"

export interface TextAreaProps {
  readonly label: string
  readonly value: string
  readonly onChange: (value: string) => void
  readonly placeholder?: string | undefined
  readonly maxLength?: number | undefined
  readonly minRows?: number | undefined
  readonly hint?: string | undefined
  readonly error?: string | undefined
  readonly disabled?: boolean | undefined
  readonly className?: string | undefined
  readonly hideLabel?: boolean | undefined
  readonly required?: boolean | undefined
  readonly onKeyDown?: ((event: KeyboardEvent<HTMLTextAreaElement>) => void) | undefined
}

const DEFAULT_ROWS = 3

export function TextArea({
  label,
  value,
  onChange,
  placeholder,
  maxLength,
  minRows = DEFAULT_ROWS,
  hint,
  error,
  disabled,
  className,
  hideLabel = false,
  required,
  onKeyDown,
}: TextAreaProps) {
  const areaRef = useRef<HTMLTextAreaElement | null>(null)

  useLayoutEffect(() => {
    const area = areaRef.current
    if (area === null || value === undefined) return
    area.style.blockSize = "auto"
    area.style.blockSize = `${area.scrollHeight}px`
  }, [value])

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
        <textarea
          {...control}
          ref={areaRef}
          className={styles.area}
          rows={minRows}
          value={value}
          placeholder={placeholder}
          maxLength={maxLength}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={onKeyDown}
        />
      )}
    </Field>
  )
}
