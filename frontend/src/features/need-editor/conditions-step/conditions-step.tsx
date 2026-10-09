import type { WorkFormat } from "@/shared/api"
import { useTranslation } from "@/shared/i18n"
import { ChoiceTiles, NumberField, TextField } from "@/shared/ui"
import type { NeedErrors, NeedForm } from "../need-form"
import styles from "./conditions-step.module.css"

const FORMATS: readonly {
  readonly value: WorkFormat
  readonly icon: "company" | "city" | "globe"
}[] = [
  { value: "office", icon: "company" },
  { value: "hybrid", icon: "city" },
  { value: "remote", icon: "globe" },
]

export interface ConditionsStepProps {
  readonly form: NeedForm
  readonly errors: NeedErrors
  readonly uncertain: ReadonlySet<string>
  readonly onChange: (patch: Partial<NeedForm>) => void
}

export function ConditionsStep({ form, errors, uncertain, onChange }: ConditionsStepProps) {
  const { t } = useTranslation(["need", "common", "catalog"])
  const flag = (field: string) => (uncertain.has(field) ? t("text.uncertain") : undefined)
  return (
    <div className={styles.step}>
      <ChoiceTiles
        legend={t("conditions.format")}
        columns="compact"
        layout="inline"
        value={form.format}
        onChange={(format) => onChange({ format })}
        tiles={FORMATS.map((item) => ({
          value: item.value,
          icon: item.icon,
          title: t(`catalog:workFormat.${item.value}` as never),
          badge: item.value === form.format ? flag("work_format") : undefined,
        }))}
      />
      {form.format === "remote" ? null : (
        <TextField
          label={t("conditions.city")}
          value={form.city}
          onChange={(city) => onChange({ city })}
          hint={flag("city") ?? t("conditions.cityHint")}
          icon="city"
          maxLength={100}
          error={errors.city === undefined ? undefined : t("errors.city")}
          className={styles.city}
        />
      )}
      <fieldset className={styles.salary}>
        <legend className={styles.legend}>{t("conditions.salary")}</legend>
        <div className={styles.range}>
          <NumberField
            label={t("common:money.fieldFrom")}
            value={form.salaryFrom}
            onChange={(salaryFrom) => onChange({ salaryFrom })}
            min={0}
            step={10000}
          />
          <NumberField
            label={t("common:money.fieldTo")}
            value={form.salaryTo}
            onChange={(salaryTo) => onChange({ salaryTo })}
            min={0}
            step={10000}
            error={errors.salary === undefined ? undefined : t("errors.salaryOrder")}
          />
        </div>
        <p className={styles.hint}>{flag("salary") ?? t("conditions.salaryHint")}</p>
      </fieldset>
    </div>
  )
}
