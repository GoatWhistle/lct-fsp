import { TextField } from "../text-field/text-field"
import { formatPhone, nextPhone } from "./format-phone"

export interface PhoneFieldProps {
  readonly label: string
  readonly value: string
  readonly onChange: (value: string) => void
  readonly hint?: string | undefined
  readonly error?: string | undefined
  readonly placeholder?: string | undefined
}

export function PhoneField({ label, value, onChange, hint, error, placeholder }: PhoneFieldProps) {
  const shown = formatPhone(value)
  return (
    <TextField
      label={label}
      type="tel"
      inputMode="tel"
      icon="phone"
      autoComplete="tel"
      value={shown}
      onChange={(typed) => onChange(nextPhone(shown, typed))}
      maxLength={18}
      placeholder={placeholder}
      hint={hint}
      error={error}
    />
  )
}
