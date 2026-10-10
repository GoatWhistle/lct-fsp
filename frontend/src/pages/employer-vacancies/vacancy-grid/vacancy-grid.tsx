import type { ReactNode } from "react"
import { useApplications } from "@/entities/application"
import { COMPANY_DIALOG_LINK } from "@/entities/company"
import { useOwnVacancies } from "@/entities/vacancy"
import { VacancyCard } from "@/features/vacancy-editor"
import type { Vacancy } from "@/shared/api"
import { useTranslation } from "@/shared/i18n"
import { ButtonLink, EmptyState, LoadError, Skeleton } from "@/shared/ui"
import styles from "./vacancy-grid.module.css"

export type VacancyTab = "published" | "archived"

export interface VacancyGridProps {
  readonly tab: VacancyTab
  readonly noCompany: boolean
  readonly create: ReactNode
  readonly onEdit: (vacancy: Vacancy) => void
}

function useCounts(): ReadonlyMap<string, number> {
  const applications = useApplications()
  const counts = new Map<string, number>()
  for (const item of applications.data ?? [])
    counts.set(item.vacancy_id, (counts.get(item.vacancy_id) ?? 0) + 1)
  return counts
}

export function isShown(vacancy: Vacancy, tab: VacancyTab): boolean {
  return (vacancy.archived_at === null) === (tab === "published")
}

export function VacancyGrid({ tab, noCompany, create, onEdit }: VacancyGridProps) {
  const { t } = useTranslation("vacancyEditor")
  const vacancies = useOwnVacancies()
  const counts = useCounts()
  if (vacancies.isError)
    return (
      <LoadError
        error={vacancies.error}
        onRetry={() => void vacancies.refetch()}
        pending={vacancies.isFetching}
      />
    )
  if (vacancies.data === undefined) return <Skeleton shape="block" />
  const shown = vacancies.data.filter((vacancy) => isShown(vacancy, tab))
  if (shown.length === 0) {
    const action = noCompany ? (
      <ButtonLink to={COMPANY_DIALOG_LINK} icon="company">
        {t("toCompany")}
      </ButtonLink>
    ) : tab === "published" ? (
      create
    ) : undefined
    return (
      <EmptyState
        icon="vacancy"
        title={t(`empty.${tab}.title`)}
        description={t(noCompany ? "needCompany" : `empty.${tab}.text`)}
        action={action}
      />
    )
  }
  return (
    <div className={styles.grid}>
      {shown.map((vacancy, index) => (
        <VacancyCard
          key={vacancy.id}
          vacancy={vacancy}
          applications={counts.get(vacancy.id) ?? 0}
          index={index}
          onEdit={onEdit}
        />
      ))}
    </div>
  )
}
