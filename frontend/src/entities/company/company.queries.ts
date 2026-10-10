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

export function useRequestDomainCheck() {
  return useMutation({
    mutationFn: (input: { readonly email: string; readonly locale: "ru" | "en" }) =>
      unwrap(api.POST("/api/employer/company/domain", { body: input })),
  })
}

export function useConfirmDomain() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (token: string) =>
      unwrap(api.POST("/api/company-domain/confirm", { body: { token } })),
    onSuccess: (company) => client.setQueryData(COMPANY_KEY, company),
  })
}
