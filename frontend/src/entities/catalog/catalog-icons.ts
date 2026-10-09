import type { IconName } from "@/shared/ui"

const SPECIALIZATION_ICON: Readonly<Record<string, IconName>> = {
  backend: "backend",
  frontend: "frontend",
  "data-ml": "data-ml",
  qa: "qa",
  devops: "devops",
}

const GRADE_ICON: Readonly<Record<string, IconName>> = {
  intern: "grade-1",
  junior: "grade-2",
  middle: "grade-3",
  senior: "grade-4",
}

export function specializationIcon(code: string): IconName {
  return SPECIALIZATION_ICON[code] ?? "measure"
}

export function gradeIcon(code: string): IconName {
  return GRADE_ICON[code] ?? "grade-1"
}
