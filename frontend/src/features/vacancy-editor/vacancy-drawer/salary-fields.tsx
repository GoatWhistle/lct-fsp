import { useTranslation } from "@/shared/i18n"
import { Icon, NumberField } from "@/shared/ui"
import styles from "./vacancy-drawer.module.css"

const SALARY_STEP = 5000

export interface SalaryFieldsProps {
  readonly from: number | null
  readonly to: number | null
  readonly onChange: (from: number | null, to: number | null) => void
  readonly error?: string | undefined
}

export function SalaryFields({ from, to, onChange, error }: SalaryFieldsProps) {
  const { t } = useTranslation(["vacancyEditor", "common"])
  return (
    <fieldset className={styles.salary}>
      <legend className={styles.legend}>{t("fields.salary")}</legend>
      <div className={styles.pair}>
        <NumberField
          label={t("common:money.fieldFrom")}
          value={from}
          onChange={(value) => onChange(value, to)}
          min={0}
          step={SALARY_STEP}
        />
        <NumberField
          label={t("common:money.fieldTo")}
          value={to}
          onChange={(value) => onChange(from, value)}
          min={0}
          step={SALARY_STEP}
        />
      </div>
      {error === undefined ? null : (
        <p className={styles.error} role="alert">
          <Icon name="alert" size="sm" />
          {error}
        </p>
      )}
      <p className={styles.basis}>{t("common:money.basis")}</p>
    </fieldset>
  )
}
