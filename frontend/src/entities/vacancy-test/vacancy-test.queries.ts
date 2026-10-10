import { useQuery } from "@tanstack/react-query"
import { api, unwrap } from "@/shared/api"

export function vacancyTestKey(needId: string) {
  return ["employer", "needs", needId, "test"] as const
}

export function useVacancyTestPreview(needId: string, enabled = true) {
  return useQuery({
    queryKey: vacancyTestKey(needId),
    queryFn: () =>
      unwrap(
        api.GET("/api/employer/needs/{need_id}/test", { params: { path: { need_id: needId } } }),
      ),
    enabled,
    staleTime: Number.POSITIVE_INFINITY,
  })
}
