import type { Profile } from "@/shared/api"

export function completeness(profile: Profile | null): number {
  if (profile === null) return 0
  const filled = [
    profile.full_name.trim() !== "",
    profile.contact_email.trim() !== "",
    profile.contact_phone !== null || profile.telegram !== null,
    profile.about.trim() !== "",
    profile.stack.length > 0,
    profile.job_roles.length > 0,
    profile.soft_skills.length > 0,
    profile.work_formats.length > 0,
    profile.city !== null,
    profile.industries.length > 0,
    profile.salary_from > 0,
  ]
  return filled.filter(Boolean).length / filled.length
}
