import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api, type CompanyInput, unwrap } from "@/shared/api"

export const COMPANY_KEY = ["employer", "company"] as const

export function useCompany() {
  return useQuery({
    queryKey: COMPANY_KEY,
    queryFn: () => unwrap(api.GET("/api/employer/company")),
  })
}

export function useSaveCompany() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: CompanyInput) => unwrap(api.PUT("/api/employer/company", { body: input })),
    onSuccess: (company) => client.setQueryData(COMPANY_KEY, company),
  })
}
