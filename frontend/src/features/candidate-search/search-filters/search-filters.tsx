import { useMemo } from "react"
import { useGrades, useSpecializations, useTechnologies } from "@/entities/catalog"
import { useCatalogNames, useTranslation } from "@/shared/i18n"
import { Button, Card, Checkbox, Combobox, Select } from "@/shared/ui"
import type { SearchState } from "../search-params"
import styles from "./search-filters.module.css"

export interface SearchFiltersProps {
  readonly state: SearchState
  readonly onChange: (state: SearchState) => void
}

const EMPTY: SearchState = {
  specialization: null,
  grade: null,
  stack: [],
  fsp: false,
  confident: false,
}

export function SearchFilters({ state, onChange }: SearchFiltersProps) {
  const { t } = useTranslation("search")
  const names = useCatalogNames()
  const specializations = useSpecializations()
  const grades = useGrades()
  const technologies = useTechnologies()
  const stackOptions = useMemo(
    () =>
      (technologies.data ?? [])
        .filter(
          (tech) =>
            state.specialization === null ||
            tech.topics.some((topic) => topic.startsWith(`${state.specialization}.`)),
        )
        .map((tech) => ({ value: tech.code, label: tech.name })),
    [technologies.data, state.specialization],
  )
  const dirty = state.stack.length > 0 || state.fsp || state.confident

  return (
    <Card
      as="aside"
      level="inner"
      title={t("filters.title")}
      className={styles.panel}
      actions={
        dirty ? (
          <Button
            variant="ghost"
            size="compact"
            icon="retry"
            onClick={() =>
              onChange({ ...EMPTY, specialization: state.specialization, grade: state.grade })
            }
          >
            {t("filters.reset")}
          </Button>
        ) : null
      }
    >
      <div className={styles.body}>
        <Select
          label={t("filters.specialization")}
          placeholder={t("filters.pick")}
          value={state.specialization}
          onChange={(specialization) => onChange({ ...state, specialization, stack: [] })}
          options={(specializations.data ?? []).map((item) => ({
            value: item.code,
            label: names.specialization(item),
          }))}
        />
        <Select
          label={t("filters.grade")}
          placeholder={t("filters.pick")}
          value={state.grade}
          onChange={(grade) => onChange({ ...state, grade })}
          options={(grades.data ?? []).map((item) => ({
            value: item.code,
            label: names.grade(item),
          }))}
        />
        <Combobox
          label={t("filters.stack")}
          values={state.stack}
          options={stackOptions}
          onChange={(stack) => onChange({ ...state, stack })}
        />
        <Checkbox
          label={t("filters.fsp")}
          checked={state.fsp}
          onChange={(fsp) => onChange({ ...state, fsp })}
        />
        <Checkbox
          label={t("filters.confident")}
          hint={t("filters.confidentHint")}
          checked={state.confident}
          onChange={(confident) => onChange({ ...state, confident })}
        />
      </div>
    </Card>
  )
}
