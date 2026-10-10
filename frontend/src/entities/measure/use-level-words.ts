import { useCallback } from "react"
import type { Level } from "@/shared/api"
import { useCatalogNames, useTranslation } from "@/shared/i18n"
import { isGradeCode, uncertaintySize } from "./grade-scale"

export interface LevelWords {
  readonly band: (band: Level["band"]) => string
  readonly uncertainty: (sd: number) => string
  readonly describe: (level: Level) => string
}

export function useLevelWords(): LevelWords {
  const { t } = useTranslation("measure")
  const names = useCatalogNames()

  const gradeWord = useCallback(
    (code: string) => (code === "intern" ? names.grade(code).toLowerCase() : names.grade(code)),
    [names],
  )

  const band = useCallback(
    (value: Level["band"]) => {
      const { low, high, confident } = value
      if (confident)
        return low === null ? t("level.below") : t("level.confident", { grade: gradeWord(low) })
      if (low === null) return t("level.internOrBelow")
      const lowWord = isGradeCode(low) ? t(`gradeWith.${low}`) : low
      return t("level.between", { low: lowWord, high: gradeWord(high ?? "") })
    },
    [t, gradeWord],
  )

  const uncertainty = useCallback((sd: number) => t(`uncertainty.${uncertaintySize(sd)}`), [t])

  const describe = useCallback(
    (level: Level) =>
      t("ruler.label", { words: band(level.band), uncertainty: uncertainty(level.theta_sd) }),
    [t, band, uncertainty],
  )

  return { band, uncertainty, describe }
}
