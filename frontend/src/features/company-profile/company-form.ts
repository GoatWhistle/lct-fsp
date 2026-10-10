import type { Company, CompanyInput, CompanySize } from "@/shared/api"
import { isPhoneComplete, normalizeLinkUrl } from "@/shared/ui"

export const COMPANY_SIZES: readonly CompanySize[] = [
  "up_to_50",
  "up_to_200",
  "up_to_1000",
  "over_1000",
]

export const BENEFITS = [
  "health",
  "education",
  "conferences",
  "equipment",
  "sport",
  "meals",
  "relocation",
] as const

export type Benefit = (typeof BENEFITS)[number]

export const MAX_LINKS = 6

export interface CompanyForm {
  readonly name: string
  readonly industry: string | null
  readonly description: string
  readonly website: string
  readonly email: string
  readonly phone: string
  readonly size: CompanySize | null
  readonly accredited: boolean
  readonly benefits: readonly string[]
  readonly links: readonly string[]
}

export type CompanyField =
  | "name"
  | "industry"
  | "description"
  | "website"
  | "email"
  | "phone"
  | "links"

export type CompanyErrors = Readonly<Record<CompanyField, boolean>>

export const EMPTY_COMPANY: CompanyForm = {
  name: "",
  industry: null,
  description: "",
  website: "",
  email: "",
  phone: "",
  size: null,
  accredited: false,
  benefits: [],
  links: [],
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
    size: company.size,
    accredited: company.it_accredited,
    benefits: company.benefits,
    links: company.links,
  }
}

export function filledLinks(links: readonly string[]): string[] {
  return links.map((link) => link.trim()).filter((link) => link !== "")
}

export function badLink(link: string): boolean {
  return link.trim() !== "" && normalizeLinkUrl(link) === null
}

export function companyErrors(form: CompanyForm): CompanyErrors {
  const website = form.website.trim()
  return {
    name: form.name.trim() === "",
    industry: form.industry === null,
    description: form.description.trim() === "",
    website: website !== "" && !WEBSITE.test(website),
    email: !EMAIL.test(form.email.trim()),
    phone: form.phone.trim() !== "" && !isPhoneComplete(form.phone),
    links: form.links.some(badLink),
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
    size: form.size,
    it_accredited: form.accredited,
    benefits: [...form.benefits],
    links: filledLinks(form.links),
  }
}

function sameList(left: readonly string[], right: readonly string[]): boolean {
  return left.length === right.length && left.every((item, index) => item === right[index])
}

export function sameForm(left: CompanyForm, right: CompanyForm): boolean {
  return (Object.keys(left) as (keyof CompanyForm)[]).every((key) => {
    const a = left[key]
    const b = right[key]
    return Array.isArray(a) && Array.isArray(b) ? sameList(a, b) : a === b
  })
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
