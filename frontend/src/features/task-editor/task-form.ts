import type { RegularTask, TaskInput, TaskKind } from "@/shared/api"

export const MAX_TOPICS = 3

export const RUBRIC = [0, 1, 2, 3] as const

export type RubricScore = (typeof RUBRIC)[number]

export interface TaskForm {
  readonly specialization: string | null
  readonly grade: string | null
  readonly kind: TaskKind
  readonly prompt: string
  readonly topics: readonly string[]
  readonly reference: string
}

export type TaskField = "specialization" | "grade" | "prompt" | "topics" | "reference"

export function formOf(task: RegularTask | null): TaskForm {
  return {
    specialization: task?.specialization.code ?? null,
    grade: task?.grade.code ?? null,
    kind: task?.kind ?? "reference",
    prompt: task?.prompt ?? "",
    topics: task?.topics.map((topic) => topic.code) ?? [],
    reference: task?.reference_answer ?? "",
  }
}

export function taskErrors(form: TaskForm): Record<TaskField, boolean> {
  return {
    specialization: form.specialization === null,
    grade: form.grade === null,
    prompt: form.prompt.trim() === "",
    topics: form.topics.length === 0 || form.topics.length > MAX_TOPICS,
    reference: form.kind === "reference" && form.reference.trim() === "",
  }
}

export function inputOf(form: TaskForm): TaskInput | null {
  const { specialization, grade } = form
  if (Object.values(taskErrors(form)).some(Boolean)) return null
  if (specialization === null || grade === null) return null
  return {
    specialization,
    grade,
    kind: form.kind,
    prompt: form.prompt.trim(),
    topics: [...form.topics],
    reference_answer: form.kind === "reference" ? form.reference.trim() : null,
  }
}
