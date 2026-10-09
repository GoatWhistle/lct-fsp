import { SkillList } from "@/entities/measure"
import type { CandidatePath } from "@/shared/api"
import { useFormatters, useTranslation } from "@/shared/i18n"
import { Card } from "@/shared/ui"
import styles from "../../../shared/styles/layout.module.css"
import { TestResult } from "../test-result/test-result"

export interface NoCategoryStepProps {
  readonly path: CandidatePath
}

export function NoCategoryStep({ path }: NoCategoryStepProps) {
  const { t } = useTranslation("path")
  const format = useFormatters()
  const date = path.retest_after === null ? "" : format.date(path.retest_after)
  return (
    <Card title={t("none.title")} description={t("none.text", { date })} className={styles.enter}>
      <div className={styles.stack}>
        {path.result === null ? null : <TestResult result={path.result} />}
        {path.profile === null ? null : (
          <Card level="inner" title={t("none.profile")}>
            <SkillList topics={path.profile.topics} label={t("none.profile")} />
          </Card>
        )}
      </div>
    </Card>
  )
}
