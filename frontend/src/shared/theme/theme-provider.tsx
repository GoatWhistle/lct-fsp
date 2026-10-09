import {
  createContext,
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
} from "react"
import { withViewTransition } from "@/shared/motion"
import {
  applyTheme,
  readThemeChoice,
  storeThemeChoice,
  subscribeSystemTheme,
  systemTheme,
  type Theme,
} from "./theme"

export interface ThemeState {
  readonly theme: Theme
  readonly setTheme: (theme: Theme) => void
}

export const ThemeContext = createContext<ThemeState | null>(null)

export interface ThemeProviderProps {
  readonly children: ReactNode
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  const [choice, setChoice] = useState<Theme | null>(readThemeChoice)
  const system = useSyncExternalStore(subscribeSystemTheme, systemTheme, () => "light" as const)
  const theme = choice ?? system

  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  const setTheme = useCallback((next: Theme) => {
    storeThemeChoice(next)
    void withViewTransition("theme", () => {
      setChoice(next)
      applyTheme(next)
    })
  }, [])

  const value = useMemo(() => ({ theme, setTheme }), [theme, setTheme])
  return <ThemeContext value={value}>{children}</ThemeContext>
}
