import { useState } from "react"
import { useNavigate } from "react-router"
import { usePath } from "@/entities/candidate-path"
import { useMyApplications, usePublishedVacancies } from "@/entities/vacancy"
import type { Application, Vacancy } from "@/shared/api"
import { useTranslation } from "@/shared/i18n"
import { Button, EmptyState, LoadError, Skeleton } from "@/shared/ui"
import { ALL, activeCount, initialFilters, matches, type VacancyFilterState } from "../filter-state"
import { VacancyCard } from "../vacancy-card/vacancy-card"
import { VacancyDrawer } from "../vacancy-drawer/vacancy-drawer"
import { VacancyFilters } from "../vacancy-filters/vacancy-filters"
import styles from "./vacancy-board.module.css"

export interface VacancyBoardProps {
  readonly selectedId: string | null
}

const BASE = "/candidate/vacancies"

function useApplicationsByVacancy(): ReadonlyMap<string, Application> {
  const applications = useMyApplications()
  return new Map((applications.data ?? []).map((item) => [item.vacancy_id, item]))
}

interface ResultsProps {
  readonly shown: readonly Vacancy[]
  readonly applied: ReadonlyMap<string, Application>
  readonly filtered: boolean
  readonly onReset: () => void
}

function Results({ shown, applied, filtered, onReset }: ResultsProps) {
  const { t } = useTranslation(["vacancies", "common"])
  if (shown.length === 0)
    return (
      <EmptyState
        icon="vacancy"
        title={t("empty.title")}
        description={t(filtered ? "empty.filtered" : "empty.text")}
        action={
          filtered ? (
            <Button variant="secondary" icon="refresh" onClick={onReset}>
              {t("filters.reset")}
            </Button>
          ) : undefined
        }
      />
    )
  return (
    <>
      <p className={styles.count}>{t("count", { count: shown.length })}</p>
      <div className={styles.grid}>
        {shown.map((vacancy, index) => (
          <VacancyCard
            key={vacancy.id}
            vacancy={vacancy}
            application={applied.get(vacancy.id)}
            to={`${BASE}/${vacancy.id}`}
            index={index}
          />
        ))}
      </div>
      <p className={styles.basis}>{t("common:money.basis")}</p>
    </>
  )
}

interface BoardProps extends VacancyBoardProps {
  readonly defaults: VacancyFilterState
}

function Board({ selectedId, defaults }: BoardProps) {
  const navigate = useNavigate()
  const [filters, setFilters] = useState(defaults)
  const vacancies = usePublishedVacancies(
    filters.specialization === ALL ? null : filters.specialization,
  )
  const applied = useApplicationsByVacancy()
  const selected = vacancies.data?.find((vacancy) => vacancy.id === selectedId)
  const reset = () => setFilters(defaults)
  const changed = activeCount(filters, defaults)
  return (
    <div className={styles.board}>
      <VacancyFilters
        value={filters}
        onChange={setFilters}
        onReset={reset}
        changed={changed}
        className={styles.filters}
      />
      <div className={styles.results} data-stale={vacancies.isPlaceholderData}>
        {vacancies.isError ? (
          <LoadError
            error={vacancies.error}
            onRetry={() => void vacancies.refetch()}
            pending={vacancies.isFetching}
          />
        ) : vacancies.data === undefined ? (
          <Skeleton shape="block" />
        ) : (
          <Results
            shown={vacancies.data.filter((vacancy) => matches(vacancy, filters))}
            applied={applied}
            filtered={changed > 0}
            onReset={reset}
          />
        )}
      </div>
      <VacancyDrawer
        vacancy={selected}
        application={selected === undefined ? undefined : applied.get(selected.id)}
        onClose={() => navigate(BASE)}
      />
    </div>
  )
}

export function VacancyBoard({ selectedId }: VacancyBoardProps) {
  const path = usePath()
  if (path.data === undefined && !path.isError) return <Skeleton shape="block" />
  const specialization = path.data?.category?.specialization.code ?? null
  return <Board selectedId={selectedId} defaults={initialFilters(specialization)} />
}
