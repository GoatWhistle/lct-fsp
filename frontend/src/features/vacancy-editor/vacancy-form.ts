import type { Vacancy, VacancyInput, WorkFormat } from "@/shared/api"

export interface VacancyForm {
  readonly title: string
  readonly description: string
  readonly specialization: string | null
  readonly grade: string | null
  readonly formats: readonly WorkFormat[]
  readonly salaryFrom: number | null
  readonly salaryTo: number | null
}

export type VacancyField = "title" | "specialization" | "grade" | "formats" | "salary"

export const WORK_FORMATS: readonly WorkFormat[] = ["office", "hybrid", "remote"]

export const EMPTY_VACANCY: VacancyForm = {
  title: "",
  description: "",
  specialization: null,
  grade: null,
  formats: [],
  salaryFrom: null,
  salaryTo: null,
}

export function formOf(vacancy: Vacancy | null): VacancyForm {
  if (vacancy === null) return EMPTY_VACANCY
  return {
    title: vacancy.title,
    description: vacancy.description,
    specialization: vacancy.specialization.code,
    grade: vacancy.grade.code,
    formats: vacancy.work_formats,
    salaryFrom: vacancy.salary_from,
    salaryTo: vacancy.salary_to,
  }
}

export function vacancyErrors(form: VacancyForm): Record<VacancyField, boolean> {
  const salaryMissing = form.salaryFrom === null || form.salaryTo === null
  return {
    title: form.title.trim() === "",
    specialization: form.specialization === null,
    grade: form.grade === null,
    formats: form.formats.length === 0,
    salary:
      salaryMissing || (form.salaryFrom ?? 0) <= 0 || (form.salaryFrom ?? 0) > (form.salaryTo ?? 0),
  }
}

export function inputOf(form: VacancyForm): VacancyInput | null {
  const { specialization, grade, salaryFrom, salaryTo } = form
  if (Object.values(vacancyErrors(form)).some(Boolean)) return null
  if (specialization === null || grade === null || salaryFrom === null || salaryTo === null)
    return null
  return {
    title: form.title.trim(),
    description: form.description.trim(),
    specialization,
    grade,
    work_formats: WORK_FORMATS.filter((format) => form.formats.includes(format)),
    salary_from: salaryFrom,
    salary_to: salaryTo,
  }
}

export function toggleFormat(formats: readonly WorkFormat[], format: WorkFormat): WorkFormat[] {
  return formats.includes(format) ? formats.filter((item) => item !== format) : [...formats, format]
}
