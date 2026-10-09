import { GradeRuler, TrustBadge } from "@/entities/measure"
import type { TopicLevel } from "@/shared/api"
import { useCatalogNames, useTranslation } from "@/shared/i18n"
import { staggerStyle } from "@/shared/motion"
import { Disclosure, IconLabel } from "@/shared/ui"
import { BlockButton } from "../block-button/block-button"
import styles from "./skill-panel.module.css"

export interface TopicRowProps {
  readonly topic: TopicLevel
  readonly index: number
  readonly widest: boolean
}

export function TopicRow({ topic, index, widest }: TopicRowProps) {
  const { t } = useTranslation("overview")
  const names = useCatalogNames()
  return (
    <li className={styles.row} style={staggerStyle(index)}>
      <div className={styles.rowHead}>
        <span className={styles.name}>{names.topic(topic.topic)}</span>
        <span className={styles.sources}>
          {widest ? (
            <IconLabel icon="uncertainty" tone="accent" className={styles.widest}>
              {t("skills.widest")}
            </IconLabel>
          ) : null}
          {topic.sources.map((source) => (
            <TrustBadge key={source} source={source} />
          ))}
        </span>
      </div>
      <GradeRuler level={topic.level} size="inline" caption />
      <Disclosure
        summary={<span className={styles.refine}>{t("skills.refine")}</span>}
        className={styles.more}
      >
        <div className={styles.block}>
          <p className={styles.blockText}>{t("skills.blockText")}</p>
          <BlockButton topic={topic.topic.code} />
        </div>
      </Disclosure>
    </li>
  )
}
