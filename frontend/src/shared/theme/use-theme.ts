import { use } from "react"
import { ThemeContext, type ThemeState } from "./theme-provider"

export function useTheme(): ThemeState {
  const value = use(ThemeContext)
  if (value === null) throw new Error("useTheme must be used within ThemeProvider")
  return value
}
