import type {
  DraftField,
  Need,
  NeedDraft,
  NeedInput,
  TopicImportance,
  WorkFormat,
} from "@/shared/api"

export type NeedStep = "who" | "requirements" | "conditions"

export const NEED_STEPS: readonly NeedStep[] = ["who", "requirements", "conditions"]

export interface NeedForm {
  readonly title: string
  readonly team: string
  readonly specialization: string | null
  readonly grade: string | null
  readonly stack: readonly string[]
  readonly importance: Readonly<Record<string, TopicImportance>>
  readonly format: WorkFormat
  readonly city: string
  readonly salaryFrom: number | null
  readonly salaryTo: number | null
}

export type NeedErrors = Partial<
  Record<"title" | "specialization" | "grade" | "city" | "salary", string>
>

export const EMPTY_FORM: NeedForm = {
  title: "",
  team: "",
  specialization: null,
  grade: null,
  stack: [],
  importance: {},
  format: "hybrid",
  city: "",
  salaryFrom: null,
  salaryTo: null,
}

export function formFromNeed(need: Need): NeedForm {
  return {
    title: need.title,
    team: need.team_description,
    specialization: need.specialization.code,
    grade: need.grade.code,
    stack: need.stack.map((item) => item.code),
    importance: Object.fromEntries(
      need.topics.filter((row) => row.edited).map((row) => [row.topic.code, row.importance]),
    ),
    format: need.work_format,
    city: need.city ?? "",
    salaryFrom: need.salary_from,
    salaryTo: need.salary_to,
  }
}

export function formFromDraft(draft: NeedDraft): NeedForm {
  return {
    ...EMPTY_FORM,
    title: draft.title ?? "",
    specialization: draft.specialization?.code ?? null,
    grade: draft.grade?.code ?? null,
    stack: draft.stack.map((item) => item.code),
    format: draft.work_format ?? EMPTY_FORM.format,
    city: draft.city ?? "",
    salaryFrom: draft.salary_from,
    salaryTo: draft.salary_to,
  }
}

export function inputOf(form: NeedForm): NeedInput {
  return {
    title: form.title.trim(),
    team_description: form.team.trim(),
    specialization: form.specialization ?? "",
    grade: form.grade ?? "",
    stack: [...form.stack],
    topic_importance: { ...form.importance },
    work_format: form.format,
    city: form.format === "remote" || form.city.trim() === "" ? null : form.city.trim(),
    salary_from: form.salaryFrom,
    salary_to: form.salaryTo,
  }
}

export function stepErrors(form: NeedForm, step: NeedStep): NeedErrors {
  if (step === "who") {
    return {
      ...(form.title.trim() === "" ? { title: "title" } : {}),
      ...(form.specialization === null ? { specialization: "specialization" } : {}),
      ...(form.grade === null ? { grade: "grade" } : {}),
    }
  }
  if (step === "conditions") {
    const salaryWrong =
      form.salaryFrom !== null && form.salaryTo !== null && form.salaryTo < form.salaryFrom
    return {
      ...(form.format !== "remote" && form.city.trim() === "" ? { city: "city" } : {}),
      ...(salaryWrong ? { salary: "salaryOrder" } : {}),
    }
  }
  return {}
}

export function isComplete(form: NeedForm): boolean {
  return NEED_STEPS.every((step) => Object.keys(stepErrors(form, step)).length === 0)
}

export function draftStepOf(field: DraftField): NeedStep {
  if (field === "specialization" || field === "grade") return "who"
  if (field === "stack") return "requirements"
  return "conditions"
}
