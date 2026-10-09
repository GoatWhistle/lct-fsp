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
  resolveTheme,
  storeThemeChoice,
  subscribeSystemTheme,
  systemTheme,
  type Theme,
  type ThemeChoice,
} from "./theme"

export interface ThemeState {
  readonly choice: ThemeChoice
  readonly theme: Theme
  readonly setChoice: (choice: ThemeChoice) => void
}

export const ThemeContext = createContext<ThemeState | null>(null)

export interface ThemeProviderProps {
  readonly children: ReactNode
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  const [choice, setChoiceState] = useState<ThemeChoice>(readThemeChoice)
  const system = useSyncExternalStore(subscribeSystemTheme, systemTheme, () => "light" as const)
  const theme = choice === "system" ? system : choice

  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  const setChoice = useCallback((next: ThemeChoice) => {
    storeThemeChoice(next)
    void withViewTransition("theme", () => {
      setChoiceState(next)
      applyTheme(resolveTheme(next))
    })
  }, [])

  const value = useMemo(() => ({ choice, theme, setChoice }), [choice, theme, setChoice])
  return <ThemeContext value={value}>{children}</ThemeContext>
}
