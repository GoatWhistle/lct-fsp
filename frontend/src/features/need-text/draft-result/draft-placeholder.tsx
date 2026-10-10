import type { CSSProperties } from "react"
import type { DraftField } from "@/shared/api"
import { useTranslation } from "@/shared/i18n"
import { staggerStyle } from "@/shared/motion"
import { Card, IconLabel, type IconName, Skeleton } from "@/shared/ui"
import styles from "./draft-result.module.css"

interface Slot {
  readonly field: DraftField | "title"
  readonly icon: IconName
  readonly width: number
}

const SLOTS: readonly Slot[] = [
  { field: "title", icon: "need", width: 70 },
  { field: "specialization", icon: "candidates", width: 40 },
  { field: "grade", icon: "measure", width: 30 },
  { field: "stack", icon: "test", width: 85 },
  { field: "work_format", icon: "company", width: 35 },
  { field: "city", icon: "city", width: 45 },
  { field: "salary", icon: "money", width: 60 },
]

export interface DraftPlaceholderProps {
  readonly pending: boolean
  readonly className?: string | undefined
}

export function DraftPlaceholder({ pending, className }: DraftPlaceholderProps) {
  const { t } = useTranslation("need")
  return (
    <Card
      title={t("text.draft")}
      description={pending ? t("text.stageMatch") : t("text.emptyResult")}
      className={className}
    >
      <dl className={styles.fields} data-pending={pending}>
        {SLOTS.map((slot, index) => (
          <div key={slot.field} className={styles.field} style={staggerStyle(index)}>
            <dt>
              <IconLabel icon={slot.icon} tone="secondary" className={styles.label}>
                {t(`text.fields.${slot.field}` as never)}
              </IconLabel>
            </dt>
            <dd className={styles.value}>
              {pending ? (
                <Skeleton className={styles.slot} />
              ) : (
                <span
                  className={styles.ghost}
                  style={{ "--slot-width": `${slot.width}%` } as CSSProperties}
                />
              )}
            </dd>
          </div>
        ))}
      </dl>
    </Card>
  )
}
