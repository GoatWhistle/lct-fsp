import type { Company, CompanyInput } from "@/shared/api"

export interface CompanyForm {
  readonly name: string
  readonly industry: string | null
  readonly description: string
  readonly website: string
  readonly email: string
  readonly phone: string
}

export type CompanyField = "name" | "industry" | "description" | "website" | "email"

export type CompanyErrors = Readonly<Record<CompanyField, boolean>>

export const EMPTY_COMPANY: CompanyForm = {
  name: "",
  industry: null,
  description: "",
  website: "",
  email: "",
  phone: "",
}

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const WEBSITE = /^(https?:\/\/)?[^\s/.]+(\.[^\s/.]+)+(\/\S*)?$/i

export function formOf(company: Company | null | undefined): CompanyForm {
  if (company === null || company === undefined) return EMPTY_COMPANY
  return {
    name: company.name,
    industry: company.industry.code,
    description: company.description,
    website: company.website ?? "",
    email: company.contact_email,
    phone: company.contact_phone ?? "",
  }
}

export function companyErrors(form: CompanyForm): CompanyErrors {
  const website = form.website.trim()
  return {
    name: form.name.trim() === "",
    industry: form.industry === null,
    description: form.description.trim() === "",
    website: website !== "" && !WEBSITE.test(website),
    email: !EMAIL.test(form.email.trim()),
  }
}

export function inputOf(form: CompanyForm): CompanyInput | null {
  if (Object.values(companyErrors(form)).some(Boolean) || form.industry === null) return null
  const website = form.website.trim()
  const phone = form.phone.trim()
  return {
    name: form.name.trim(),
    industry: form.industry,
    description: form.description.trim(),
    website: website === "" ? null : website,
    contact_email: form.email.trim(),
    contact_phone: phone === "" ? null : phone,
  }
}

export function sameForm(left: CompanyForm, right: CompanyForm): boolean {
  return (Object.keys(left) as (keyof CompanyForm)[]).every((key) => left[key] === right[key])
}

export function initialsOf(name: string): string {
  const words = name
    .replace(/[«»"'.,]/g, " ")
    .split(/[\s-]+/)
    .filter((word) => word !== "")
  return words
    .slice(0, 2)
    .map((word) => word.charAt(0).toLocaleUpperCase())
    .join("")
}

export function hostOf(website: string): string {
  return website
    .trim()
    .replace(/^https?:\/\//i, "")
    .replace(/\/$/, "")
}
