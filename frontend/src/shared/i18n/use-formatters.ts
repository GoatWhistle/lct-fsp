import { useMemo } from "react"
import { createFormatters, type Formatters } from "./formatters"
import { useLocale } from "./use-locale"

export function useFormatters(): Formatters {
  const { locale } = useLocale()
  return useMemo(() => createFormatters(locale), [locale])
}
