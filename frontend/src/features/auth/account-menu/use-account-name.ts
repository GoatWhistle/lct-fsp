import { useCompany } from "@/entities/company"
import { useProfile } from "@/entities/profile"
import type { User } from "@/shared/api"

export function useAccountName(user: User): string {
  const employer = user.role === "employer"
  const company = useCompany(employer)
  const profile = useProfile(!employer)
  const name = employer ? company.data?.name : profile.data?.full_name
  const trimmed = name?.trim() ?? ""
  return trimmed === "" ? (user.email.split("@")[0] ?? user.email) : trimmed
}
