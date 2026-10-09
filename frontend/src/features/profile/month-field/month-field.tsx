import { useMemo } from "react"
import { useLocale, useTranslation } from "@/shared/i18n"
import { Select } from "@/shared/ui"
import styles from "./month-field.module.css"

const YEARS_BACK = 50
const MONTHS = 12

export interface MonthFieldProps {
  readonly label: string
  readonly value: string
  readonly onChange: (value: string) => void
  readonly error?: string | undefined
  readonly disabled?: boolean | undefined
}

function useMonthOptions() {
  const { locale } = useLocale()
  return useMemo(() => {
    const format = new Intl.DateTimeFormat(locale, { month: "long" })
    return Array.from({ length: MONTHS }, (_, index) => {
      const label = format.format(new Date(2000, index, 1))
      return {
        value: String(index + 1).padStart(2, "0"),
        label: label.charAt(0).toLocaleUpperCase(locale) + label.slice(1),
      }
    })
  }, [locale])
}

function yearOptions() {
  const current = new Date().getFullYear()
  return Array.from({ length: YEARS_BACK + 1 }, (_, index) => {
    const year = String(current - index)
    return { value: year, label: year }
  })
}

export function MonthField({ label, value, onChange, error, disabled }: MonthFieldProps) {
  const { t } = useTranslation("profile")
  const months = useMonthOptions()
  const years = useMemo(yearOptions, [])
  const [year = "", month = ""] = value === "" ? [] : value.split("-")
  const fallbackYear = years[0]?.value ?? ""
  const change = (nextYear: string, nextMonth: string) =>
    onChange(`${nextYear === "" ? fallbackYear : nextYear}-${nextMonth === "" ? "01" : nextMonth}`)
  return (
    <fieldset className={styles.field} aria-invalid={error !== undefined} disabled={disabled}>
      <legend className={styles.legend}>{label}</legend>
      <div className={styles.controls}>
        <Select
          label={t("experience.month")}
          hideLabel
          value={month === "" ? null : month}
          placeholder={t("experience.month")}
          options={months}
          onChange={(next) => change(year, next)}
          disabled={disabled}
        />
        <Select
          label={t("experience.year")}
          hideLabel
          value={year === "" ? null : year}
          placeholder={t("experience.year")}
          options={years}
          onChange={(next) => change(next, month)}
          disabled={disabled}
        />
      </div>
      {error === undefined ? null : <p className={styles.error}>{error}</p>}
    </fieldset>
  )
}
