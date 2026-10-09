export const LOCALES = ["ru", "en"] as const

export type Locale = (typeof LOCALES)[number]

export const DEFAULT_LOCALE: Locale = "ru"

export const LOCALE_STORAGE_KEY = "calibr-locale"

export const INTL_LOCALE: Readonly<Record<Locale, string>> = { ru: "ru-RU", en: "en-GB" }

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && (LOCALES as readonly string[]).includes(value)
}

function browserLocale(): Locale | null {
  const languages = globalThis.navigator?.languages ?? []
  for (const language of languages) {
    const base = language.slice(0, 2).toLowerCase()
    if (isLocale(base)) return base
  }
  return null
}

export function readStoredLocale(): Locale {
  try {
    const stored = globalThis.localStorage?.getItem(LOCALE_STORAGE_KEY)
    if (isLocale(stored)) return stored
  } catch {
    return DEFAULT_LOCALE
  }
  return browserLocale() ?? DEFAULT_LOCALE
}

export function storeLocale(locale: Locale): void {
  try {
    globalThis.localStorage?.setItem(LOCALE_STORAGE_KEY, locale)
  } catch {
    return
  }
}
