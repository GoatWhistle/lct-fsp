import type { ExperienceEntry, ExperienceEntryInput } from "@/shared/api"

export const ENTRIES_MAX = 20
export const LINE_MAX = 200
export const SUMMARY_MAX = 2000
export const STACK_MAX = 30

const MONTHS_IN_YEAR = 12
const HALF_YEAR = 6

export interface ExperienceDraft {
  readonly key: string
  readonly place: string
  readonly role: string
  readonly start: string
  readonly end: string
  readonly stack: readonly string[]
  readonly summary: string
}

export type EntryField = "place" | "start" | "end"
export type EntryErrors = Partial<Record<EntryField, "required" | "future" | "beforeStart">>

let lastKey = 0

function nextKey(): string {
  lastKey += 1
  return `entry-${lastKey}`
}

export function entryDraftOf(entry: ExperienceEntry): ExperienceDraft {
  return {
    key: nextKey(),
    place: entry.place,
    role: entry.role,
    start: entry.start,
    end: entry.end ?? "",
    stack: entry.stack.map((item) => item.code),
    summary: entry.summary,
  }
}

export function emptyEntry(): ExperienceDraft {
  return { key: nextKey(), place: "", role: "", start: "", end: "", stack: [], summary: "" }
}

export function entryInputOf(entry: ExperienceDraft): ExperienceEntryInput {
  return {
    place: entry.place.trim(),
    role: entry.role.trim(),
    start: entry.start,
    end: entry.end === "" ? null : entry.end,
    stack: [...entry.stack],
    summary: entry.summary.trim(),
  }
}

export function thisMonth(): string {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`
}

export function validateEntry(entry: ExperienceDraft): EntryErrors {
  const errors: EntryErrors = {}
  if (entry.place.trim() === "") errors.place = "required"
  if (entry.start === "") errors.start = "required"
  else if (entry.start > thisMonth()) errors.start = "future"
  if (entry.end !== "" && entry.start !== "" && entry.end < entry.start) errors.end = "beforeStart"
  return errors
}

function monthIndex(month: string): number {
  const [year, number] = month.split("-").map(Number)
  return (year ?? 0) * MONTHS_IN_YEAR + (number ?? 1) - 1
}

export interface YearsByTechnology {
  readonly code: string
  readonly years: number
}

export function technologyYears(entries: readonly ExperienceDraft[]): readonly YearsByTechnology[] {
  const now = monthIndex(thisMonth())
  const months = new Map<string, Set<number>>()
  for (const entry of entries) {
    if (entry.start === "") continue
    const from = monthIndex(entry.start)
    const to = Math.min(entry.end === "" ? now : monthIndex(entry.end), now)
    for (const code of entry.stack) {
      const set = months.get(code) ?? new Set<number>()
      for (let month = from; month <= to; month += 1) set.add(month)
      months.set(code, set)
    }
  }
  return [...months]
    .map(([code, set]) => ({
      code,
      years: Math.floor(set.size / HALF_YEAR) / 2,
    }))
    .filter((item) => item.years > 0)
    .sort((left, right) => right.years - left.years)
}
