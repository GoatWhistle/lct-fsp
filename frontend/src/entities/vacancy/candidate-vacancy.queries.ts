import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { type Application, api, unwrap } from "@/shared/api"

export const PUBLISHED_VACANCIES_KEY = ["candidate", "vacancies"] as const
export const MY_APPLICATIONS_KEY = ["candidate", "applications"] as const
const INBOX_KEY = ["candidate", "invitations"] as const

export function usePublishedVacancies(specialization: string | null) {
  return useQuery({
    queryKey: [...PUBLISHED_VACANCIES_KEY, specialization ?? "all"],
    queryFn: () =>
      unwrap(
        api.GET("/api/candidate/vacancies", {
          params: { query: specialization === null ? {} : { specialization } },
        }),
      ),
    placeholderData: (previous) => previous,
  })
}

export function useMyApplications() {
  return useQuery({
    queryKey: MY_APPLICATIONS_KEY,
    queryFn: () => unwrap(api.GET("/api/candidate/applications")),
  })
}

function useReplaceApplication() {
  const client = useQueryClient()
  return (application: Application) =>
    client.setQueryData<Application[]>(MY_APPLICATIONS_KEY, (list) => {
      if (list === undefined) return [application]
      const known = list.some((item) => item.id === application.id)
      return known
        ? list.map((item) => (item.id === application.id ? application : item))
        : [application, ...list]
    })
}

export function useApply() {
  const replace = useReplaceApplication()
  const client = useQueryClient()
  return useMutation({
    mutationFn: (vacancyId: string) =>
      unwrap(
        api.POST("/api/candidate/vacancies/{vacancy_id}/apply", {
          params: { path: { vacancy_id: vacancyId } },
        }),
      ),
    onSuccess: replace,
    onError: () => client.invalidateQueries({ queryKey: PUBLISHED_VACANCIES_KEY }),
  })
}

export function useRevokeApplication() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      unwrap(
        api.POST("/api/candidate/applications/{application_id}/revoke", {
          params: { path: { application_id: id } },
        }),
      ),
    onSettled: async () => {
      await client.invalidateQueries({ queryKey: MY_APPLICATIONS_KEY })
      await client.invalidateQueries({ queryKey: INBOX_KEY })
    },
  })
}
