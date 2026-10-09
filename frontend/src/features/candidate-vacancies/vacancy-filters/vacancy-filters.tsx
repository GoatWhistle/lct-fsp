import { useState } from "react"
import { useGrades, useSpecializations } from "@/entities/catalog"
import type { WorkFormat } from "@/shared/api"
import { useMediaQuery } from "@/shared/hooks"
import { useCatalogNames, useTranslation } from "@/shared/i18n"
import { Button, Card, Checkbox, Dialog, NumberField, Select } from "@/shared/ui"
import { ALL, type VacancyFilterState, WORK_FORMATS } from "../filter-state"
import styles from "./vacancy-filters.module.css"

const SALARY_STEP = 10000
const WIDE = "(min-width: 64rem)"

export interface VacancyFiltersProps {
  readonly value: VacancyFilterState
  readonly onChange: (next: VacancyFilterState) => void
  readonly onReset: () => void
  readonly changed: number
  readonly className?: string | undefined
}

type FieldsProps = Pick<VacancyFiltersProps, "value" | "onChange">

function Fields({ value, onChange }: FieldsProps) {
  const { t } = useTranslation(["vacancies", "catalog", "common"])
  const names = useCatalogNames()
  const specializations = useSpecializations()
  const grades = useGrades()
  const patch = (next: Partial<VacancyFilterState>) => onChange({ ...value, ...next })
  const toggle = (format: WorkFormat, on: boolean) =>
    patch({
      formats: on
        ? WORK_FORMATS.filter((item) => item === format || value.formats.includes(item))
        : value.formats.filter((item) => item !== format),
    })
  return (
    <div className={styles.fields}>
      <Select
        label={t("filters.specialization")}
        value={value.specialization}
        onChange={(specialization) => patch({ specialization })}
        options={[
          { value: ALL, label: t("filters.allSpecializations") },
          ...(specializations.data ?? []).map((item) => ({
            value: item.code,
            label: names.specialization(item),
          })),
        ]}
      />
      <Select
        label={t("filters.grade")}
        value={value.grade}
        onChange={(grade) => patch({ grade })}
        options={[
          { value: ALL, label: t("filters.allGrades") },
          ...(grades.data ?? []).map((item) => ({ value: item.code, label: names.grade(item) })),
        ]}
      />
      <fieldset className={styles.formats}>
        <legend className={styles.legend}>{t("filters.formats")}</legend>
        {WORK_FORMATS.map((format) => (
          <Checkbox
            key={format}
            label={t(`catalog:workFormat.${format}`)}
            checked={value.formats.includes(format)}
            onChange={(on) => toggle(format, on)}
          />
        ))}
      </fieldset>
      <NumberField
        label={t("filters.salary")}
        unit={t("filters.salaryUnit")}
        min={0}
        step={SALARY_STEP}
        value={value.salaryFrom}
        onChange={(salaryFrom) => patch({ salaryFrom })}
        hint={t("common:money.basis")}
      />
    </div>
  )
}

export function VacancyFilters({
  value,
  onChange,
  onReset,
  changed,
  className,
}: VacancyFiltersProps) {
  const { t } = useTranslation("vacancies")
  const wide = useMediaQuery(WIDE)
  const [open, setOpen] = useState(false)
  const reset =
    changed > 0 ? (
      <Button variant="link" size="compact" icon="refresh" onClick={onReset}>
        {t("filters.reset")}
      </Button>
    ) : undefined
  if (wide)
    return (
      <Card as="aside" title={t("filters.title")} className={className} actions={reset}>
        <Fields value={value} onChange={onChange} />
      </Card>
    )
  return (
    <div className={styles.toolbar}>
      <Button variant="secondary" icon="filter" onClick={() => setOpen(true)}>
        {changed > 0 ? t("filters.titleCount", { count: changed }) : t("filters.title")}
      </Button>
      {reset}
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        size="drawer"
        title={t("filters.title")}
        actions={
          <Button icon="check" onClick={() => setOpen(false)}>
            {t("filters.done")}
          </Button>
        }
      >
        <Fields value={value} onChange={onChange} />
      </Dialog>
    </div>
  )
}
