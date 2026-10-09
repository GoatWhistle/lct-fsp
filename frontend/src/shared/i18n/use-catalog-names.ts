import { useMemo } from "react"
import { useTranslation } from "react-i18next"

interface Named {
  readonly code: string
  readonly name: string
}

export interface CatalogNames {
  readonly specialization: (ref: Named | string) => string
  readonly grade: (ref: Named | string) => string
  readonly topic: (ref: Named | string) => string
  readonly industry: (ref: Named | string) => string
  readonly discipline: (ref: Named | string) => string
}

export function useCatalogNames(): CatalogNames {
  const { t, i18n } = useTranslation("catalog")
  return useMemo(() => {
    const name = (keyOf: (code: string) => string) => (ref: Named | string) => {
      const key = keyOf(typeof ref === "string" ? ref : ref.code)
      if (i18n.exists(key)) return t(key as never)
      return typeof ref === "string" ? ref : ref.name
    }
    return {
      specialization: name((code) => `catalog:specialization.${code}`),
      grade: name((code) => `catalog:grade.${code}`),
      topic: name((code) => `catalog:topic.${code}`),
      industry: name((code) => `catalog:industry.${code}`),
      discipline: name((code) => `catalog:discipline.${code}`),
    }
  }, [t, i18n])
}
