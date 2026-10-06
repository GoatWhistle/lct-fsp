import type { ReactNode } from 'react'
import { SALARY_BASIS } from './salary'

function Amount({
  value,
  onChange,
  required,
  min = 1,
}: {
  value: string
  onChange: (value: string) => void
  required: boolean
  min?: number | string
}) {
  return (
    <input
      type="number"
      required={required}
      min={min}
      step={1}
      inputMode="numeric"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  )
}

/** Одна сумма в рублях в месяц; подпись «до вычета НДФЛ» — в самом поле. */
export function SalaryInput({
  label,
  value,
  onChange,
  hint,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  hint?: ReactNode
}) {
  return (
    <label className="field">
      {label}, ₽ в месяц {SALARY_BASIS}
      <Amount value={value} onChange={onChange} required />
      {hint && <span className="hint">{hint}</span>}
    </label>
  )
}

export type SalaryRange = { from: string; to: string }

/**
 * Вилка «от–до» в рублях в месяц до вычета НДФЛ. Необязательная вилка указывается целиком или
 * не указывается: заполненная граница требует вторую.
 */
export function SalaryRangeInput({
  range,
  onChange,
  optional = false,
  hint,
}: {
  range: SalaryRange
  onChange: (range: SalaryRange) => void
  optional?: boolean
  hint?: ReactNode
}) {
  return (
    <fieldset className="plain">
      <legend>Вилка, ₽ в месяц {SALARY_BASIS}</legend>
      <div className="field-row">
        <label className="field">
          От
          <Amount
            value={range.from}
            onChange={(from) => onChange({ ...range, from })}
            required={!optional || range.to !== ''}
          />
        </label>
        <label className="field">
          До
          <Amount
            value={range.to}
            onChange={(to) => onChange({ ...range, to })}
            required={!optional || range.from !== ''}
            min={range.from || 1}
          />
        </label>
      </div>
      {hint && <span className="hint">{hint}</span>}
    </fieldset>
  )
}
