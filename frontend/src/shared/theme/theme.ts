export const THEME_CHOICES = ["light", "dark"] as const

export type Theme = (typeof THEME_CHOICES)[number]

export const THEME_STORAGE_KEY = "calibr-theme"

const DARK_QUERY = "(prefers-color-scheme: dark)"

export function isThemeChoice(value: unknown): value is Theme {
  return typeof value === "string" && (THEME_CHOICES as readonly string[]).includes(value)
}

export function readThemeChoice(): Theme | null {
  try {
    const stored = globalThis.localStorage?.getItem(THEME_STORAGE_KEY)
    return isThemeChoice(stored) ? stored : null
  } catch {
    return null
  }
}

export function storeThemeChoice(choice: Theme): void {
  try {
    globalThis.localStorage?.setItem(THEME_STORAGE_KEY, choice)
  } catch {
    return
  }
}

export function systemTheme(): Theme {
  return globalThis.matchMedia?.(DARK_QUERY).matches ? "dark" : "light"
}

export function subscribeSystemTheme(listener: () => void): () => void {
  const query = globalThis.matchMedia?.(DARK_QUERY)
  if (query === undefined) return () => undefined
  query.addEventListener("change", listener)
  return () => query.removeEventListener("change", listener)
}

export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme
}
