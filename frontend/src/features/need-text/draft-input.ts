import type { CatalogRef, NeedDraft, NeedInput } from "@/shared/api"

export function inputOfDraft(draft: NeedDraft): NeedInput | null {
  if (draft.title === null || draft.specialization === null || draft.grade === null) return null
  return {
    title: draft.title,
    team_description: "",
    specialization: draft.specialization.code,
    grade: draft.grade.code,
    stack: draft.stack.map((tech) => tech.code),
    topic_importance: {},
    work_format: draft.work_format ?? "hybrid",
    city: draft.work_format === "remote" ? null : draft.city,
    salary_from: draft.salary_from,
    salary_to: draft.salary_to,
  }
}

export function draftWithSpecialization(specialization: CatalogRef): NeedDraft {
  return {
    kind: "draft",
    title: null,
    specialization,
    grade: null,
    stack: [],
    work_format: null,
    city: null,
    salary_from: null,
    salary_to: null,
    confidence: {},
    uncertain: [],
    salary_basis: "gross",
  }
}
