import type { TestItem } from "@/shared/api"
import { useCatalogNames, useTranslation } from "@/shared/i18n"
import { IconLabel, Pane, ScrollArea } from "@/shared/ui"
import styles from "./condition-panel.module.css"

export interface ConditionPanelProps {
  readonly item: TestItem
}

export function ConditionPanel({ item }: ConditionPanelProps) {
  const { t } = useTranslation("test")
  const names = useCatalogNames()
  return (
    <Pane
      tone="inverse"
      className={styles.panel}
      title={t("condition")}
      leading={
        <span className={styles.number} aria-hidden="true">
          {String(item.number).padStart(2, "0")}
        </span>
      }
      meta={
        <IconLabel icon="topic" className={styles.topic}>
          {names.topic(item.topic)}
        </IconLabel>
      }
    >
      <p className={styles.prompt}>{item.prompt}</p>
      {item.code === null ? null : (
        <div className={styles.code}>
          <ScrollArea label={t("code")}>
            <pre className={styles.listing}>
              <code>{item.code}</code>
            </pre>
          </ScrollArea>
        </div>
      )}
    </Pane>
  )
}
