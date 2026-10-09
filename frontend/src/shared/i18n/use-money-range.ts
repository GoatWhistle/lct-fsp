import { useCallback } from "react"
import { useTranslation } from "react-i18next"
import { useFormatters } from "./use-formatters"

export function useMoneyRange(): (from: number | null, to: number | null) => string | null {
  const { t } = useTranslation()
  const format = useFormatters()
  return useCallback(
    (from: number | null, to: number | null) => {
      if (from !== null && to !== null)
        return t("money.range", { from: format.money(from), to: format.money(to) })
      if (from !== null) return t("money.from", { from: format.money(from) })
      return null
    },
    [t, format],
  )
}
