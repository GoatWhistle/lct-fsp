import { useSelections } from "@/entities/selection"
import type { SelectionSummary } from "@/shared/api"

const RECENT = 100

export type LatestSelections = ReadonlyMap<string, SelectionSummary>

export function useRecentSelections() {
  return useSelections(null, RECENT)
}

export function latestByNeed(selections: readonly SelectionSummary[]): LatestSelections {
  const latest = new Map<string, SelectionSummary>()
  for (const selection of selections) {
    if (selection.need_id !== null && !latest.has(selection.need_id))
      latest.set(selection.need_id, selection)
  }
  return latest
}

export function candidateCount(selection: SelectionSummary): number {
  return selection.exact_total + selection.nearby_total
}
