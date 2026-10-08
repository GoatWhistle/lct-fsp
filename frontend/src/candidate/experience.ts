import type { ExperienceEntry, ExperienceEntryInput } from '../api/client'

/**
 * Запись опыта в форме: месяцы — `ГГГГ-ММ` из поля «месяц», пустой конец — по сейчас. `key` —
 * только для React: у записи нет id, а индекс съезжает при удалении.
 */
export type EntryDraft = {
  key: number
  place: string
  role: string
  start: string
  end: string
  stack: string[]
  summary: string
}

let lastKey = 0

export function entryDraftOf(entry: ExperienceEntry): EntryDraft {
  return {
    key: ++lastKey,
    place: entry.place,
    role: entry.role,
    start: entry.start,
    end: entry.end ?? '',
    stack: entry.stack.map((t) => t.code),
    summary: entry.summary,
  }
}

export function entryInputOf(entry: EntryDraft): ExperienceEntryInput {
  const { place, role, start, end, stack, summary } = entry
  return { place, role, start, end: end || null, stack, summary }
}

export function emptyEntry(): EntryDraft {
  return { key: ++lastKey, place: '', role: '', start: '', end: '', stack: [], summary: '' }
}

/** Текущий месяц `ГГГГ-ММ` по местному времени. */
export function thisMonth(): string {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}
