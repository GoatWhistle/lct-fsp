import type { CandidatePath } from "@/shared/api"
import { useCatalogNames, useTranslation } from "@/shared/i18n"
import { Trace, type TraceStatus } from "@/shared/ui"

const ORDER = ["direction", "grade", "test", "category"] as const

const STAGE_INDEX: Readonly<Record<CandidatePath["stage"], number>> = {
  survey: 0,
  grade: 1,
  test: 2,
  offer: 2,
  no_category: 3,
  category: 4,
  verification: 3,
}

export function PathTrace({ path }: { readonly path: CandidatePath }) {
  const { t } = useTranslation("path")
  const names = useCatalogNames()
  const current = STAGE_INDEX[path.stage]
  const notes: Readonly<Record<(typeof ORDER)[number], string | undefined>> = {
    direction: path.survey === null ? undefined : names.specialization(path.survey.specialization),
    grade: path.attempt === null ? undefined : names.grade(path.attempt.grade),
    test: undefined,
    category: undefined,
  }
  const status = (index: number): TraceStatus =>
    index < current ? "done" : index === current ? "current" : "upcoming"
  return (
    <Trace
      label={t("steps.label")}
      animate
      steps={ORDER.map((step, index) => ({
        key: step,
        status: status(index),
        title: t(`steps.${step}`),
        description: notes[step],
      }))}
    />
  )
}
