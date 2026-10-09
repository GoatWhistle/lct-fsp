import type { WorkFormat } from "@/shared/api"
import { useFormatters, useTranslation } from "@/shared/i18n"

export function useWorkFormats(): (formats: readonly WorkFormat[]) => string {
  const { t, i18n } = useTranslation("catalog")
  const format = useFormatters()
  return (formats) =>
    format.list(
      formats.map((item, index) => {
        const name = t(`workFormat.${item}`)
        return index === 0 ? name : name.toLocaleLowerCase(i18n.language)
      }),
    )
}
