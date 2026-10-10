import type {
  HideableField,
  Profile,
  ProfileInput,
  ResumeDraft,
  ResumeField,
  WorkFormat,
} from "@/shared/api"
import { isPhoneComplete } from "@/shared/ui"
import { type ExperienceDraft, entryDraftOf, entryInputOf } from "./experience"

export interface ProfileDraft {
  readonly full_name: string
  readonly contact_email: string
  readonly contact_phone: string
  readonly telegram: string
  readonly about: string
  readonly stack: readonly string[]
  readonly job_roles: string
  readonly experience_years: number | null
  readonly soft_skills: string
  readonly experience: readonly ExperienceDraft[]
  readonly work_formats: readonly WorkFormat[]
  readonly city: string
  readonly relocation: boolean
  readonly industries: readonly string[]
  readonly salary_from: number | null
  readonly hidden: readonly HideableField[]
}

export type DraftPatch = Partial<ProfileDraft>
export type DraftField = keyof ProfileDraft
export type DraftErrors = Partial<Record<DraftField, string>>

export const HIDEABLE: readonly HideableField[] = [
  "stack",
  "experience_years",
  "city",
  "relocation",
  "industries",
]

const LIST_SEPARATOR = /[,;\n]/

function joinList(items: readonly string[]): string {
  return items.join(", ")
}

export function splitList(text: string): string[] {
  return text
    .split(LIST_SEPARATOR)
    .map((item) => item.trim())
    .filter((item) => item !== "")
}

export function draftOf(profile: Profile | null, email: string): ProfileDraft {
  if (profile === null)
    return {
      full_name: "",
      contact_email: email,
      contact_phone: "",
      telegram: "",
      about: "",
      stack: [],
      job_roles: "",
      experience_years: null,
      soft_skills: "",
      experience: [],
      work_formats: [],
      city: "",
      relocation: false,
      industries: [],
      salary_from: null,
      hidden: [],
    }
  return {
    full_name: profile.full_name,
    contact_email: profile.contact_email,
    contact_phone: profile.contact_phone ?? "",
    telegram: profile.telegram === null ? "" : `@${profile.telegram}`,
    about: profile.about,
    stack: profile.stack.map((item) => item.code),
    job_roles: joinList(profile.job_roles),
    experience_years: profile.experience_years,
    soft_skills: joinList(profile.soft_skills),
    experience: profile.experience.map(entryDraftOf),
    work_formats: profile.work_formats,
    city: profile.city ?? "",
    relocation: profile.relocation,
    industries: profile.industries.map((item) => item.code),
    salary_from: profile.salary_from,
    hidden: profile.hidden,
  }
}

function blankToNull(text: string): string | null {
  const trimmed = text.trim()
  return trimmed === "" ? null : trimmed
}

export function inputOf(draft: ProfileDraft): ProfileInput {
  const city = blankToNull(draft.city)
  return {
    full_name: draft.full_name.trim(),
    contact_email: draft.contact_email.trim(),
    contact_phone: blankToNull(draft.contact_phone),
    telegram: blankToNull(draft.telegram),
    about: draft.about.trim(),
    stack: [...draft.stack],
    job_roles: splitList(draft.job_roles),
    experience_years: draft.experience_years ?? 0,
    soft_skills: splitList(draft.soft_skills),
    experience: draft.experience.map(entryInputOf),
    work_formats: [...draft.work_formats],
    city,
    relocation: draft.relocation,
    industries: [...draft.industries],
    salary_from: draft.salary_from ?? 0,
    hidden: draft.hidden.filter((field) => field !== "city" || city !== null),
  }
}

export function needsCity(draft: ProfileDraft): boolean {
  return draft.work_formats.some((format) => format !== "remote")
}

export function validate(draft: ProfileDraft): readonly DraftField[] {
  const missing: DraftField[] = []
  if (draft.full_name.trim() === "") missing.push("full_name")
  if (draft.contact_email.trim() === "") missing.push("contact_email")
  if (draft.contact_phone.trim() !== "" && !isPhoneComplete(draft.contact_phone))
    missing.push("contact_phone")
  if (draft.experience_years === null) missing.push("experience_years")
  if (draft.work_formats.length === 0) missing.push("work_formats")
  if (needsCity(draft) && draft.city.trim() === "") missing.push("city")
  if (draft.salary_from === null || draft.salary_from <= 0) missing.push("salary_from")
  return missing
}

export function withResume(draft: ProfileDraft, parsed: ResumeDraft): ProfileDraft {
  return {
    ...draft,
    full_name: parsed.full_name ?? draft.full_name,
    contact_email: parsed.contact_email ?? draft.contact_email,
    contact_phone: parsed.contact_phone ?? draft.contact_phone,
    telegram: parsed.telegram === null ? draft.telegram : `@${parsed.telegram}`,
    stack: parsed.stack.length > 0 ? parsed.stack.map((item) => item.code) : draft.stack,
    job_roles: parsed.job_roles.length > 0 ? joinList(parsed.job_roles) : draft.job_roles,
    experience_years: parsed.experience_years ?? draft.experience_years,
    soft_skills: parsed.soft_skills.length > 0 ? joinList(parsed.soft_skills) : draft.soft_skills,
    experience:
      parsed.experience.length > 0 ? parsed.experience.map(entryDraftOf) : draft.experience,
  }
}

export function recognizedFields(parsed: ResumeDraft): readonly ResumeField[] {
  return Object.keys(parsed.confidence) as ResumeField[]
}

export function sameDraft(left: ProfileDraft, right: ProfileDraft): boolean {
  return JSON.stringify(left) === JSON.stringify(right)
}

export type FieldMark = "recognized" | "uncertain"

export interface DraftSectionProps {
  readonly draft: ProfileDraft
  readonly onChange: (patch: DraftPatch) => void
  readonly errors: DraftErrors
  readonly marks: ReadonlyMap<string, FieldMark>
}
