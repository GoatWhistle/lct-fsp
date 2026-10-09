import { clsx } from "clsx"
import { useTranslation } from "react-i18next"
import { Icon } from "../../primitives/icon/icon"
import { NumberField } from "../number-field/number-field"
import styles from "./salary-input.module.css"

export interface SalaryInputProps {
  readonly label: string
  readonly from: number | null
  readonly to: number | null
  readonly onChange: (from: number | null, to: number | null) => void
  readonly step?: number
  readonly error?: string | undefined
  readonly className?: string | undefined
}

export function SalaryInput({
  label,
  from,
  to,
  onChange,
  step = 10000,
  error,
  className,
}: SalaryInputProps) {
  const { t } = useTranslation("common")
  return (
    <fieldset className={clsx(styles.salary, className)}>
      <legend className={styles.legend}>{label}</legend>
      <div className={styles.pair}>
        <NumberField
          label={t("money.fieldFrom")}
          value={from}
          onChange={(value) => onChange(value, to)}
          min={0}
          step={step}
        />
        <NumberField
          label={t("money.fieldTo")}
          value={to}
          onChange={(value) => onChange(from, value)}
          min={0}
          step={step}
        />
      </div>
      {error === undefined ? null : (
        <p className={styles.error} role="alert">
          <Icon name="alert" size="sm" />
          {error}
        </p>
      )}
      <p className={styles.basis}>{t("money.basis")}</p>
    </fieldset>
  )
}
