import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { type Application, api, unwrap } from "@/shared/api"

export const APPLICATIONS_KEY = ["employer", "applications"] as const

export type ApplicationAction = "view" | "accept" | "decline"

export function useApplications() {
  return useQuery({
    queryKey: APPLICATIONS_KEY,
    queryFn: () => unwrap(api.GET("/api/employer/applications")),
  })
}

function request(action: ApplicationAction, id: string) {
  const params = { params: { path: { application_id: id } } }
  if (action === "view") return api.POST("/api/employer/applications/{application_id}/view", params)
  if (action === "accept")
    return api.POST("/api/employer/applications/{application_id}/accept", params)
  return api.POST("/api/employer/applications/{application_id}/decline", params)
}

export function useApplicationAction(action: ApplicationAction) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => unwrap(request(action, id)),
    onSuccess: (application) =>
      client.setQueryData<Application[]>(APPLICATIONS_KEY, (list) =>
        list?.map((item) => (item.id === application.id ? application : item)),
      ),
    onError: () => client.invalidateQueries({ queryKey: APPLICATIONS_KEY }),
  })
}
