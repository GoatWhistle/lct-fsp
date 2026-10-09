import { useInfiniteQuery, useQuery } from "@tanstack/react-query"
import { api, type CandidateFilters, unwrap } from "@/shared/api"
import { SELECTION_PAGE } from "./selection.queries"

const EMPTY_FILTERS: CandidateFilters = { fsp_confirmed: false, confident: false }

export function useCandidateSearch(filters: CandidateFilters | null) {
  return useInfiniteQuery({
    queryKey: ["employer", "search", filters],
    initialPageParam: 0,
    enabled: filters !== null,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.POST("/api/employer/candidates/search", {
          params: { query: { offset: pageParam, limit: SELECTION_PAGE } },
          body: filters ?? EMPTY_FILTERS,
        }),
      ),
    getNextPageParam: (last) => {
      const next = last.offset + last.entries.length
      return last.entries.length === 0 || next >= last.total ? undefined : next
    },
  })
}

export function useCandidateCard(id: string) {
  return useQuery({
    queryKey: ["employer", "candidate", id],
    queryFn: () =>
      unwrap(
        api.GET("/api/employer/candidates/{candidate_id}", {
          params: { path: { candidate_id: id } },
        }),
      ),
  })
}
