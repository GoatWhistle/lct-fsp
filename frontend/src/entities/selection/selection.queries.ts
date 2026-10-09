import {
  type InfiniteData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import {
  api,
  type CandidateFilters,
  type NeedInput,
  type Selection,
  type SelectionOrder,
  unwrap,
} from "@/shared/api"

export const SELECTION_PAGE = 20
export const SELECTIONS_KEY = ["employer", "selections"] as const

export const ORDERS: readonly SelectionOrder[] = ["mutual", "match"]

export function selectionKey(id: string) {
  return [...SELECTIONS_KEY, id] as const
}

export function orderedKey(id: string, order: SelectionOrder) {
  return order === "mutual" ? selectionKey(id) : ([...selectionKey(id), "order", order] as const)
}

export function filteredTotal(selection: Selection): number {
  return (
    selection.filtered_exact_total +
    selection.filtered_nearby_total +
    selection.filtered_unconfirmed_total
  )
}

export function useSelection(id: string, order: SelectionOrder = "mutual") {
  return useInfiniteQuery({
    queryKey: orderedKey(id, order),
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/api/employer/selections/{selection_id}", {
          params: {
            path: { selection_id: id },
            query: { offset: pageParam, limit: SELECTION_PAGE, order },
          },
        }),
      ),
    getNextPageParam: (last: Selection) => {
      const next = last.offset + last.entries.length
      return last.entries.length === 0 || next >= filteredTotal(last) ? undefined : next
    },
  })
}

export function useSelections(needId: string | null) {
  return useQuery({
    queryKey: [...SELECTIONS_KEY, "list", needId],
    queryFn: () =>
      unwrap(api.GET("/api/employer/selections", { params: { query: { need_id: needId } } })),
  })
}

function useSeed() {
  const client = useQueryClient()
  return (selection: Selection) => {
    client.setQueryData<InfiniteData<Selection, number>>(selectionKey(selection.id), {
      pages: [selection],
      pageParams: [0],
    })
    return client.invalidateQueries({ queryKey: [...SELECTIONS_KEY, "list"] })
  }
}

export function useBuildSelection() {
  const seed = useSeed()
  return useMutation({
    mutationFn: (needId: string) =>
      unwrap(
        api.POST("/api/employer/needs/{need_id}/selections", {
          params: { path: { need_id: needId }, query: { limit: SELECTION_PAGE } },
        }),
      ),
    onSuccess: seed,
  })
}

export function useBuildDraftSelection() {
  const seed = useSeed()
  return useMutation({
    mutationFn: (input: NeedInput) =>
      unwrap(
        api.POST("/api/employer/selections", {
          params: { query: { limit: SELECTION_PAGE } },
          body: input,
        }),
      ),
    onSuccess: seed,
  })
}

export function useApplyFilters(id: string) {
  const client = useQueryClient()
  const seedMutual = useSeed()
  const seed = (selection: Selection) => {
    void client.invalidateQueries({ queryKey: orderedKey(id, "match") })
    return seedMutual(selection)
  }
  return useMutation({
    mutationFn: (filters: CandidateFilters) =>
      unwrap(
        api.PUT("/api/employer/selections/{selection_id}/filters", {
          params: { path: { selection_id: id }, query: { limit: SELECTION_PAGE } },
          body: filters,
        }),
      ),
    onSuccess: seed,
  })
}

export function useShortlist(id: string) {
  return useQuery({
    queryKey: [...selectionKey(id), "shortlist"],
    queryFn: () =>
      unwrap(
        api.GET("/api/employer/selections/{selection_id}/shortlist", {
          params: { path: { selection_id: id } },
        }),
      ),
  })
}

export interface ShortlistToggle {
  readonly candidate: string
  readonly on: boolean
}

export function useToggleShortlist(id: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ candidate, on }: ShortlistToggle) => {
      const params = { path: { selection_id: id, candidate_id: candidate } }
      const path = "/api/employer/selections/{selection_id}/shortlist/{candidate_id}" as const
      return unwrap(on ? api.PUT(path, { params }) : api.DELETE(path, { params }))
    },
    onSuccess: (shortlist) => {
      client.setQueryData([...selectionKey(id), "shortlist"], shortlist)
      const ids = shortlist.entries.map((entry) => entry.candidate_id)
      for (const order of ORDERS) {
        client.setQueryData<InfiniteData<Selection, number>>(orderedKey(id, order), (data) =>
          data === undefined
            ? data
            : { ...data, pages: data.pages.map((page) => ({ ...page, shortlist: ids })) },
        )
      }
    },
  })
}
