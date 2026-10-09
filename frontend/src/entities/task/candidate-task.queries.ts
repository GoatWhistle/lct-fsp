import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api, type CatalogTask, type OwnAnswer, unwrap } from "@/shared/api"

export const TASK_CATALOG_KEY = ["candidate", "tasks"] as const
export const MY_ANSWERS_KEY = ["candidate", "tasks", "answers"] as const

export interface TaskFilters {
  readonly grade: string | null
  readonly topic: string | null
}

export interface TaskAnswer {
  readonly taskId: string
  readonly response: string
}

export function useTaskCatalog(filters: TaskFilters, enabled = true) {
  return useQuery({
    queryKey: [...TASK_CATALOG_KEY, "catalog", filters.grade ?? "all", filters.topic ?? "all"],
    queryFn: () =>
      unwrap(
        api.GET("/api/candidate/tasks", {
          params: {
            query: {
              ...(filters.grade === null ? {} : { grade: filters.grade }),
              ...(filters.topic === null ? {} : { topic: filters.topic }),
            },
          },
        }),
      ),
    placeholderData: (previous) => previous,
    enabled,
  })
}

export function useMyAnswers(enabled = true) {
  return useQuery({
    queryKey: MY_ANSWERS_KEY,
    queryFn: () => unwrap(api.GET("/api/candidate/tasks/answers")),
    enabled,
  })
}

export function useAnswerTask() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ taskId, response }: TaskAnswer) =>
      unwrap(
        api.POST("/api/candidate/tasks/{task_id}/answer", {
          params: { path: { task_id: taskId } },
          body: { response },
        }),
      ),
    onSuccess: (answer) => {
      client.setQueryData<OwnAnswer[]>(MY_ANSWERS_KEY, (list) =>
        list === undefined ? undefined : [answer, ...list],
      )
      client.setQueriesData<CatalogTask[]>({ queryKey: [...TASK_CATALOG_KEY, "catalog"] }, (list) =>
        list?.filter((task) => task.id !== answer.task.id),
      )
    },
    onError: () => client.invalidateQueries({ queryKey: TASK_CATALOG_KEY }),
  })
}
