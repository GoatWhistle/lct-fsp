import { GradeProbabilities, GradeRuler } from "@/entities/measure"
import type { TestResult as Result } from "@/shared/api"
import { useTranslation } from "@/shared/i18n"
import { Card, Chip } from "@/shared/ui"
import styles from "../../../shared/styles/layout.module.css"

export interface TestResultProps {
  readonly result: Result
  readonly highlight?: string | null
  readonly animate?: boolean
  readonly expressLimit?: number | undefined
}

export function TestResult({ result, highlight, animate = false, expressLimit }: TestResultProps) {
  const { t } = useTranslation("path")
  const express = expressLimit !== undefined
  return (
    <Card
      level="inner"
      title={t("result.level")}
      description={express ? t("express.note", { limit: expressLimit }) : undefined}
      actions={
        express ? (
          <Chip tone="accent" icon="measure">
            {t("express.badge")}
          </Chip>
        ) : undefined
      }
    >
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
