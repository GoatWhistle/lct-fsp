import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api, unwrap, type Vacancy, type VacancyInput } from "@/shared/api"

export const OWN_VACANCIES_KEY = ["employer", "vacancies"] as const

export interface SaveVacancy {
  readonly id: string | null
  readonly input: VacancyInput
}

export function useOwnVacancies() {
  return useQuery({
    queryKey: OWN_VACANCIES_KEY,
    queryFn: () => unwrap(api.GET("/api/employer/vacancies")),
  })
}

function useReplace() {
  const client = useQueryClient()
  return (vacancy: Vacancy) =>
    client.setQueryData<Vacancy[]>(OWN_VACANCIES_KEY, (list) => {
      if (list === undefined) return [vacancy]
      const known = list.some((item) => item.id === vacancy.id)
      return known
        ? list.map((item) => (item.id === vacancy.id ? vacancy : item))
        : [vacancy, ...list]
    })
}

export function useSaveVacancy() {
  const replace = useReplace()
  return useMutation({
    mutationFn: ({ id, input }: SaveVacancy) =>
      unwrap(
        id === null
          ? api.POST("/api/employer/vacancies", { body: input })
          : api.PUT("/api/employer/vacancies/{vacancy_id}", {
              params: { path: { vacancy_id: id } },
              body: input,
            }),
      ),
    onSuccess: replace,
  })
}

export function useArchiveVacancy() {
  const replace = useReplace()
  return useMutation({
    mutationFn: (id: string) =>
      unwrap(
        api.POST("/api/employer/vacancies/{vacancy_id}/archive", {
          params: { path: { vacancy_id: id } },
        }),
      ),
    onSuccess: replace,
  })
}
