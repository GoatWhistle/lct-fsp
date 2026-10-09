import type { CandidateFilters } from "@/shared/api"

export interface SearchState {
  readonly specialization: string | null
  readonly grade: string | null
  readonly stack: readonly string[]
  readonly fsp: boolean
  readonly confident: boolean
}

export function stateOf(params: URLSearchParams): SearchState {
  const stack = params.get("stack")
  return {
    specialization: params.get("spec"),
    grade: params.get("grade"),
    stack: stack === null || stack === "" ? [] : stack.split(","),
    fsp: params.get("fsp") === "1",
    confident: params.get("confident") === "1",
  }
}

export function paramsOf(state: SearchState): URLSearchParams {
  const params = new URLSearchParams()
  if (state.specialization !== null) params.set("spec", state.specialization)
  if (state.grade !== null) params.set("grade", state.grade)
  if (state.stack.length > 0) params.set("stack", state.stack.join(","))
  if (state.fsp) params.set("fsp", "1")
  if (state.confident) params.set("confident", "1")
  return params
}

export function filtersOf(state: SearchState): CandidateFilters | null {
  if (state.specialization === null || state.grade === null) return null
  return {
    specialization: state.specialization,
    grade: state.grade,
    stack: [...state.stack],
    fsp_confirmed: state.fsp,
    confident: state.confident,
    grade_status: [],
  }
}
