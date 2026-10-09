import type { CandidateFilters, GradeStatusKind } from "@/shared/api"
import { useTranslation } from "@/shared/i18n"
import { Button, Card, Checkbox, Combobox, type ComboboxOption, Spinner } from "@/shared/ui"
import styles from "./filters-panel.module.css"

const STATUSES: readonly GradeStatusKind[] = ["confirmed", "below_claimed", "unconfirmed"]

export interface FiltersPanelProps {
  readonly filters: CandidateFilters
  readonly stackOptions: readonly ComboboxOption[]
  readonly pending: boolean
  readonly onChange: (filters: CandidateFilters) => void
  readonly onReset: () => void
}

export function isFiltered(filters: CandidateFilters): boolean {
  return (
    (filters.stack ?? []).length > 0 ||
    filters.fsp_confirmed ||
    filters.confident ||
    (filters.grade_status ?? []).length > 0
  )
}

export function FiltersPanel({
  filters,
  stackOptions,
  pending,
  onChange,
  onReset,
}: FiltersPanelProps) {
  const { t } = useTranslation(["selection", "measure"])
  const statuses = filters.grade_status ?? []
  const toggleStatus = (status: GradeStatusKind, on: boolean) =>
    onChange({
      ...filters,
      grade_status: on ? [...statuses, status] : statuses.filter((item) => item !== status),
    })

  return (
    <Card
      as="aside"
      level="inner"
      title={t("filters.title")}
      className={styles.panel}
      actions={
        pending ? (
          <Spinner size="sm" delayed label={t("filters.applying")} />
        ) : isFiltered(filters) ? (
          <Button variant="ghost" size="compact" icon="retry" onClick={onReset}>
            {t("filters.reset")}
          </Button>
        ) : null
      }
    >
      <div className={styles.body}>
        <Combobox
          label={t("filters.stack")}
          values={filters.stack ?? []}
          options={stackOptions}
          onChange={(stack) => onChange({ ...filters, stack: [...stack] })}
        />
        <Checkbox
          label={t("filters.fsp")}
          checked={filters.fsp_confirmed}
          onChange={(fsp_confirmed) => onChange({ ...filters, fsp_confirmed })}
        />
        <Checkbox
          label={t("filters.confident")}
          hint={t("filters.confidentHint")}
          checked={filters.confident}
          onChange={(confident) => onChange({ ...filters, confident })}
        />
        <fieldset className={styles.group}>
          <legend className={styles.legend}>{t("filters.status")}</legend>
          {STATUSES.map((status) => (
            <Checkbox
              key={status}
              label={t(`selection:filterStatus.${status}` as never)}
              checked={statuses.includes(status)}
              onChange={(on) => toggleStatus(status, on)}
            />
          ))}
        </fieldset>
      </div>
    </Card>
  )
}
