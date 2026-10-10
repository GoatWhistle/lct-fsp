import { useIndustries } from "@/entities/catalog"
import type { WorkFormat } from "@/shared/api"
import { useCatalogNames, useTranslation } from "@/shared/i18n"
import { ChoiceTiles, Combobox, FlagRow, Icon, NumberField, Switch, TextField } from "@/shared/ui"
import { EditorSection } from "../editor-section/editor-section"
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
  const toggle = (format: WorkFormat) =>
    onChange({
      work_formats: draft.work_formats.includes(format)
        ? draft.work_formats.filter((item) => item !== format)
        : FORMATS.filter((item) => item === format || draft.work_formats.includes(item)),
    })
  return (
    <EditorSection id="expectations" title={t("sections.expectations")}>
      <div className={styles.formats}>
        <ChoiceTiles<WorkFormat>
          legend={t("fields.formats")}
          layout="inline"
          columns="compact"
          value={null}
          selected={draft.work_formats}
          onChange={toggle}
          required
          tiles={FORMATS.map((format) => ({
            value: format,
            title: catalog(`workFormat.${format}`),
            icon: `format-${format}`,
          }))}
        />
        {errors.work_formats === undefined ? null : (
          <p className={styles.error}>{errors.work_formats}</p>
        )}
      </div>
      <div className={styles.grid}>
        <TextField
          label={t("fields.city")}
          icon="city"
          autoComplete="address-level2"
          value={draft.city}
          onChange={(city) => onChange({ city })}
          placeholder={t("fields.cityPlaceholder")}
          error={errors.city}
          required={needsCity(draft)}
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
          required
        />
      </div>
      <FlagRow
        mark={<Icon name="benefit-relocation" size="md" />}
        title={t("fields.relocation")}
        note={t("fields.relocationNote")}
        active={draft.relocation}
        trailing={
          <Switch
            label={t("fields.relocation")}
            hideLabel
            checked={draft.relocation}
            onChange={(relocation) => onChange({ relocation })}
          />
        }
      />
      {industries.data === undefined ? null : (
        <Combobox
          label={t("fields.industries")}
          values={draft.industries}
          onChange={(values) => onChange({ industries: values })}
          placeholder={t("fields.industriesPlaceholder")}
          className={styles.wide}
          options={industries.data.map((item) => ({
            value: item.code,
            label: names.industry(item),
          }))}
        />
      )}
    </EditorSection>
  )
}
