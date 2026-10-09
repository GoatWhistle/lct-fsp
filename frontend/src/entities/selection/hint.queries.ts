import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { api, unwrap } from "@/shared/api"
import { isSalaryRange } from "@/shared/i18n"
import { SELECTIONS_KEY } from "./selection.queries"

export function useSalaryHint(
  selectionId: string | null,
  candidateId: string,
  from: number | null,
  to: number | null,
) {
  return useQuery({
    queryKey: [...SELECTIONS_KEY, "hint", selectionId, candidateId, from, to],
    enabled: selectionId !== null && isSalaryRange(from, to),
    placeholderData: keepPreviousData,
    queryFn: () =>
      unwrap(
        api.GET("/api/employer/selections/{selection_id}/candidates/{candidate_id}/salary-hint", {
          params: {
            path: { selection_id: selectionId ?? "", candidate_id: candidateId },
            query: { salary_from: from ?? 0, salary_to: to ?? 0 },
          },
        }),
      ),
  })
}
