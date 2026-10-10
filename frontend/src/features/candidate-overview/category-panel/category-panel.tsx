import { GradeRuler, TrustBadge } from "@/entities/measure"
import type { CandidatePath } from "@/shared/api"
import { useFormatters, useTranslation } from "@/shared/i18n"
import { Card, IconLabel, StatusBadge } from "@/shared/ui"
import { CategoryBadges } from "../category-badges/category-badges"
import { GradeUp, StepDownMenu } from "../grade-change/grade-change"
import styles from "./category-panel.module.css"

export interface CategoryPanelProps {
  readonly path: CandidatePath
  readonly motionIndex?: number
  readonly className?: string | undefined
}

export function CategoryPanel({ path, motionIndex, className }: CategoryPanelProps) {
  const { t } = useTranslation("overview")
  const format = useFormatters()
  const level = path.profile?.overall ?? path.result?.overall ?? null
  if (path.category === null) return null
  return (
    <Card motionIndex={motionIndex} className={className} aria-label={t("category.title")}>
      <div className={styles.bar}>
        <div className={styles.identity}>
          <CategoryBadges category={path.category} size="large" />
          <div className={styles.status}>
            <StatusBadge tone="positive" icon="verification">
              {t("category.confirmed")}
            </StatusBadge>
            <IconLabel icon="calendar" tone="secondary" className={styles.since}>
              {t("category.since", { date: format.date(path.category.assigned_at) })}
            </IconLabel>
            {path.category.verified_at ? <TrustBadge source="verification" /> : null}
          </div>
        </div>
        <div className={styles.level}>{level === null ? null : <GradeRuler level={level} />}</div>
        <div className={styles.actions}>
          <GradeUp path={path} />
          <StepDownMenu path={path} />
        </div>
      </div>
    </Card>
  )
}
