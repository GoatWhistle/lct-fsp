import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api, type Company, type CompanyInput, unwrap } from "@/shared/api"

export const COMPANY_KEY = ["employer", "company"] as const

export type LogoChange =
  | { readonly kind: "keep" }
  | { readonly kind: "remove" }
  | {
      readonly kind: "upload"
      readonly file: File
    }

export const KEEP_LOGO: LogoChange = { kind: "keep" }

export function useCompany(enabled = true) {
  return useQuery({
    queryKey: COMPANY_KEY,
    enabled,
    queryFn: () => unwrap(api.GET("/api/employer/company")),
  })
}

function applyLogo(change: LogoChange): Promise<Company> | null {
  if (change.kind === "remove") return unwrap(api.DELETE("/api/employer/company/logo"))
  if (change.kind === "keep") return null
  return unwrap(
    api.PUT("/api/employer/company/logo", {
      body: "",
      bodySerializer: () => change.file,
      headers: { "Content-Type": change.file.type },
    }),
  )
}

export interface SaveCompanyInput {
  readonly input: CompanyInput
  readonly logo: LogoChange
}

export function useSaveCompany() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: async ({ input, logo }: SaveCompanyInput) => {
      const saved = await unwrap(api.PUT("/api/employer/company", { body: input }))
      return (await applyLogo(logo)) ?? saved
    },
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
