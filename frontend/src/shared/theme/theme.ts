export const THEME_CHOICES = ["light", "dark", "system"] as const

export type ThemeChoice = (typeof THEME_CHOICES)[number]

export type Theme = "light" | "dark"

export const THEME_STORAGE_KEY = "calibr-theme"

const DARK_QUERY = "(prefers-color-scheme: dark)"

export function isThemeChoice(value: unknown): value is ThemeChoice {
  return typeof value === "string" && (THEME_CHOICES as readonly string[]).includes(value)
}

export function readThemeChoice(): ThemeChoice {
  try {
    const stored = globalThis.localStorage?.getItem(THEME_STORAGE_KEY)
    return isThemeChoice(stored) ? stored : "system"
  } catch {
    return "system"
  }
}

export function storeThemeChoice(choice: ThemeChoice): void {
  try {
    globalThis.localStorage?.setItem(THEME_STORAGE_KEY, choice)
  } catch {
    return
  }
}

export function systemTheme(): Theme {
  return globalThis.matchMedia?.(DARK_QUERY).matches ? "dark" : "light"
}

export function resolveTheme(choice: ThemeChoice): Theme {
  return choice === "system" ? systemTheme() : choice
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
