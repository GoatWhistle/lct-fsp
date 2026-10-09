import { useIndustries } from "@/entities/catalog"
import type { WorkFormat } from "@/shared/api"
import { useCatalogNames, useTranslation } from "@/shared/i18n"
import { Checkbox, Combobox, IconLabel, NumberField, Switch, TextField } from "@/shared/ui"
import { EditorSection, FieldRow } from "../editor-section/editor-section"
import { type DraftSectionProps, needsCity } from "../profile-draft"
import styles from "./expectations-section.module.css"

const FORMATS: readonly WorkFormat[] = ["office", "hybrid", "remote"]
const SALARY_STEP = 10000

export function ExpectationsSection({ draft, onChange, errors }: DraftSectionProps) {
  const { t } = useTranslation("profile")
  const catalog = useTranslation("catalog").t
  const common = useTranslation().t
  const names = useCatalogNames()
  const industries = useIndustries()
  const toggle = (format: WorkFormat, on: boolean) =>
    onChange({
      work_formats: on
        ? FORMATS.filter((item) => item === format || draft.work_formats.includes(item))
        : draft.work_formats.filter((item) => item !== format),
    })
  return (
    <EditorSection id="expectations" title={t("sections.expectations")}>
      <fieldset className={styles.formats} aria-invalid={errors.work_formats !== undefined}>
        <legend className={styles.legend}>{t("fields.formats")}</legend>
        <div className={styles.options}>
          {FORMATS.map((format) => (
            <Checkbox
              key={format}
              label={catalog(`workFormat.${format}`)}
              checked={draft.work_formats.includes(format)}
              onChange={(on) => toggle(format, on)}
            />
          ))}
        </div>
        {errors.work_formats === undefined ? null : (
          <p className={styles.error}>{errors.work_formats}</p>
        )}
      </fieldset>
      <FieldRow>
        <TextField
          label={t("fields.city")}
          icon="city"
          autoComplete="address-level2"
          value={draft.city}
          onChange={(city) => onChange({ city })}
          hint={needsCity(draft) ? t("fields.cityRequired") : t("fields.cityHint")}
          error={errors.city}
        />
        <NumberField
          label={t("fields.salary")}
          unit={t("fields.salaryUnit")}
          min={0}
          step={SALARY_STEP}
          value={draft.salary_from}
          onChange={(salary_from) => onChange({ salary_from })}
          hint={common("money.basis")}
          error={errors.salary_from}
        />
      </FieldRow>
      <IconLabel icon="lock" tone="secondary" className={styles.note}>
        {t("fields.salaryNote")}
      </IconLabel>
      <Switch
        label={t("fields.relocation")}
        checked={draft.relocation}
        onChange={(relocation) => onChange({ relocation })}
      />
      {industries.data === undefined ? null : (
        <Combobox
          label={t("fields.industries")}
          values={draft.industries}
          onChange={(values) => onChange({ industries: values })}
          options={industries.data.map((item) => ({
            value: item.code,
            label: names.industry(item),
          }))}
          hint={t("fields.industriesHint")}
        />
      )}
    </EditorSection>
  )
}
