import { useCallback } from "react"
import { useTranslation } from "@/shared/i18n"
import type { FieldMark } from "./profile-draft"

export function useFieldHint(
  marks: ReadonlyMap<string, FieldMark>,
): (field: string, base?: string) => string | undefined {
  const { t } = useTranslation("profile")
  return useCallback(
    (field: string, base?: string) => {
      const mark = marks.get(field)
      if (mark === "uncertain") return t("resume.uncertain")
      if (mark === "recognized") return base ?? t("resume.recognized")
      return base
    },
    [marks, t],
  )
}
