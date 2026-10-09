import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query"
import { type AuthorAnswer, api, type RegularTask, type TaskInput, unwrap } from "@/shared/api"

export const OWN_TASKS_KEY = ["employer", "tasks"] as const

export interface SaveTask {
  readonly id: string | null
  readonly input: TaskInput
}

export interface GradeAnswer {
  readonly answerId: string
  readonly rubric: number
}

const answersKey = (taskId: string) => [...OWN_TASKS_KEY, taskId, "answers"] as const

export function useOwnTasks() {
  return useQuery({
    queryKey: OWN_TASKS_KEY,
    queryFn: () => unwrap(api.GET("/api/employer/tasks")),
  })
}

function useReplace() {
  const client = useQueryClient()
  return (task: RegularTask) =>
    client.setQueryData<RegularTask[]>(OWN_TASKS_KEY, (list) => {
      if (list === undefined) return [task]
      const known = list.some((item) => item.id === task.id)
      return known ? list.map((item) => (item.id === task.id ? task : item)) : [task, ...list]
    })
}

export function useSaveTask() {
  const replace = useReplace()
  return useMutation({
    mutationFn: ({ id, input }: SaveTask) =>
      unwrap(
        id === null
          ? api.POST("/api/employer/tasks", { body: input })
          : api.PUT("/api/employer/tasks/{task_id}", {
              params: { path: { task_id: id } },
              body: input,
            }),
      ),
    onSuccess: replace,
  })
}

export function useWithdrawTask() {
  const replace = useReplace()
  return useMutation({
    mutationFn: (id: string) =>
      unwrap(
        api.POST("/api/employer/tasks/{task_id}/withdraw", { params: { path: { task_id: id } } }),
      ),
    onSuccess: replace,
  })
}

export function useTaskAnswers(taskId: string, enabled: boolean) {
  return useQuery({
    queryKey: answersKey(taskId),
    queryFn: () =>
      unwrap(
        api.GET("/api/employer/tasks/{task_id}/answers", {
          params: { path: { task_id: taskId } },
        }),
      ),
    enabled,
  })
}

export function useAwaitingReview(tasks: readonly RegularTask[] | undefined): ReadonlySet<string> {
  const gradable = (tasks ?? []).filter((task) => task.kind === "open" && task.answers > 0)
  const results = useQueries({
    queries: gradable.map((task) => ({
      queryKey: answersKey(task.id),
      queryFn: () =>
        unwrap(
          api.GET("/api/employer/tasks/{task_id}/answers", {
            params: { path: { task_id: task.id } },
          }),
        ),
    })),
  })
  const waiting = gradable.filter((_, index) =>
    (results[index]?.data ?? []).some((answer) => answer.rubric === null),
  )
  return new Set(waiting.map((task) => task.id))
}

export function useGradeAnswer(taskId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ answerId, rubric }: GradeAnswer) =>
      unwrap(
        api.POST("/api/employer/tasks/{task_id}/answers/{answer_id}/grade", {
          params: { path: { task_id: taskId, answer_id: answerId } },
          body: { rubric },
        }),
      ),
    onSuccess: (answer) =>
      client.setQueryData<AuthorAnswer[]>(answersKey(taskId), (list) =>
        list?.map((item) => (item.id === answer.id ? answer : item)),
      ),
  })
}
