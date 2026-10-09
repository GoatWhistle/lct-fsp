import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { isInProgress, useSetPath } from "@/entities/candidate-path"
import { api, type CandidatePath, unwrap } from "@/shared/api"

export const ITEM_KEY = ["candidate", "path", "item"] as const

export function useTestItem() {
  return useQuery({
    queryKey: ITEM_KEY,
    queryFn: () => unwrap(api.GET("/api/candidate/path/item")),
    refetchOnWindowFocus: false,
    staleTime: Number.POSITIVE_INFINITY,
  })
}

export interface AnswerInput {
  readonly id: string
  readonly response: string
  readonly paste_events: number
  readonly focus_losses: number
}

export function useAnswer(onFinished: (path: CandidatePath) => void) {
  const client = useQueryClient()
  const setPath = useSetPath()
  return useMutation({
    mutationFn: ({ id, response, ...counters }: AnswerInput) =>
      unwrap(
        api.POST("/api/candidate/path/item/answer", {
          body: { presentation_id: id, response, ...counters },
        }),
      ),
    onSuccess: async (path) => {
      setPath(path)
      if (isInProgress(path)) await client.invalidateQueries({ queryKey: ITEM_KEY })
      else {
        client.removeQueries({ queryKey: ITEM_KEY })
        onFinished(path)
      }
    },
  })
}
