import { GradeProbabilities, GradeRuler } from "@/entities/measure"
import type { TestResult as Result } from "@/shared/api"
import { useTranslation } from "@/shared/i18n"
import { Card } from "@/shared/ui"
import styles from "../../../shared/styles/layout.module.css"

export interface TestResultProps {
  readonly result: Result
  readonly highlight?: string | null
  readonly animate?: boolean
}

export function TestResult({ result, highlight, animate = false }: TestResultProps) {
  const { t } = useTranslation("path")
  return (
    <Card level="inner" title={t("result.level")}>
      <div className={styles.stack}>
        <GradeRuler level={result.overall} animate={animate} />
        <GradeProbabilities
          items={result.grade_probabilities}
          highlight={highlight ?? result.grade}
          label={t("result.probabilities")}
          animate={animate}
        />
      </div>
    </Card>
  )
}
