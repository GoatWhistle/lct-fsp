import type { Vacancy, WorkFormat } from "@/shared/api"

export const ALL = "all"

export interface VacancyFilterState {
  readonly specialization: string
  readonly grade: string
  readonly formats: readonly WorkFormat[]
  readonly salaryFrom: number | null
}

export const WORK_FORMATS: readonly WorkFormat[] = ["office", "hybrid", "remote"]

export function initialFilters(specialization: string | null): VacancyFilterState {
  return { specialization: specialization ?? ALL, grade: ALL, formats: [], salaryFrom: null }
}

export function matches(vacancy: Vacancy, filters: VacancyFilterState): boolean {
  if (filters.grade !== ALL && vacancy.grade.code !== filters.grade) return false
  if (
    filters.formats.length > 0 &&
    !vacancy.work_formats.some((format) => filters.formats.includes(format))
  )
    return false
  return filters.salaryFrom === null || vacancy.salary_to >= filters.salaryFrom
}

export function activeCount(filters: VacancyFilterState, defaults: VacancyFilterState): number {
  return [
    filters.specialization !== defaults.specialization,
    filters.grade !== ALL,
    filters.formats.length > 0,
    filters.salaryFrom !== null,
  ].filter(Boolean).length
}
