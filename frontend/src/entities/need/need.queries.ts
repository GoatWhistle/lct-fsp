import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api, type NeedInput, unwrap } from "@/shared/api"

export const NEEDS_KEY = ["employer", "needs"] as const

export type ImportanceInput = Pick<NeedInput, "specialization" | "stack" | "topic_importance">

export function useNeeds() {
  return useQuery({
    queryKey: NEEDS_KEY,
    queryFn: () => unwrap(api.GET("/api/employer/needs")),
  })
}

export function useNeed(id: string | undefined) {
  return useQuery({
    queryKey: [...NEEDS_KEY, id],
    queryFn: () =>
      unwrap(api.GET("/api/employer/needs/{need_id}", { params: { path: { need_id: id ?? "" } } })),
    enabled: id !== undefined,
  })
}

export interface SaveNeed {
  readonly id: string | null
  readonly input: NeedInput
}

export function useSaveNeed() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, input }: SaveNeed) =>
      unwrap(
        id === null
          ? api.POST("/api/employer/needs", { body: input })
          : api.PUT("/api/employer/needs/{need_id}", {
              params: { path: { need_id: id } },
              body: input,
            }),
      ),
    onSuccess: (need) => {
      client.setQueryData([...NEEDS_KEY, need.id], need)
      return client.invalidateQueries({ queryKey: NEEDS_KEY, exact: true })
    },
  })
}

export function useDeleteNeed() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      unwrap(api.DELETE("/api/employer/needs/{need_id}", { params: { path: { need_id: id } } })),
    onSuccess: () => client.invalidateQueries({ queryKey: NEEDS_KEY }),
  })
}

export function useTopicImportance(input: ImportanceInput | null) {
  return useQuery({
    queryKey: [...NEEDS_KEY, "importance", input],
    queryFn: () =>
      unwrap(
        api.POST("/api/employer/needs/topic-importance", {
          body: input ?? { specialization: "" },
        }),
      ),
    enabled: input !== null && input.specialization !== "",
    placeholderData: keepPreviousData,
  })
}

export function useParseNeed() {
  return useMutation({
    mutationFn: (text: string) => unwrap(api.POST("/api/employer/needs/parse", { body: { text } })),
  })
}
