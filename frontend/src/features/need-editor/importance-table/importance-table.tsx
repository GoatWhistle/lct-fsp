import type { TopicImportance, TopicImportanceRow } from "@/shared/api"
import { useCatalogNames, useTranslation } from "@/shared/i18n"
import { staggerStyle } from "@/shared/motion"
import { Button, Chip, IconLabel, Segmented } from "@/shared/ui"
import styles from "./importance-table.module.css"

const LEVELS: readonly TopicImportance[] = ["key", "important", "nice"]

export interface ImportanceTableProps {
  readonly rows: readonly TopicImportanceRow[]
  readonly stale: boolean
  readonly onChange: (topic: string, importance: TopicImportance | null) => void
}

export function ImportanceTable({ rows, stale, onChange }: ImportanceTableProps) {
  const { t } = useTranslation(["need", "catalog"])
  const names = useCatalogNames()
  return (
    <ul className={styles.table} data-stale={stale} aria-busy={stale}>
      {rows.map((row, index) => {
        const topic = names.topic(row.topic)
        return (
          <li key={row.topic.code} className={styles.row} style={staggerStyle(index)}>
            <div className={styles.topic}>
              <span className={styles.name}>{topic}</span>
              <span className={styles.meta}>
                <IconLabel
                  icon={row.edited ? "edit" : "link"}
                  tone={row.edited ? "accent" : "secondary"}
                  className={styles.source}
                >
                  {row.edited ? t("requirements.edited") : t("requirements.fromStack")}
                </IconLabel>
                {row.technologies.map((tech) => (
                  <Chip key={tech.code}>{tech.name}</Chip>
                ))}
                {row.edited ? (
                  <Button
                    variant="ghost"
                    size="compact"
                    icon="retry"
                    onClick={() => onChange(row.topic.code, null)}
                    aria-label={t("requirements.resetLabel", { topic })}
                  >
                    {t("requirements.reset")}
                  </Button>
                ) : null}
              </span>
            </div>
            <Segmented
              label={topic}
              size="compact"
              value={row.importance}
              onChange={(importance) => onChange(row.topic.code, importance)}
              options={LEVELS.map((level) => ({
                value: level,
                label: t(`catalog:importance.${level}` as never),
              }))}
            />
          </li>
        )
      })}
    </ul>
  )
}
