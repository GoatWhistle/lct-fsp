import { GradeRuler, TrustBadge, useLevelWords } from "@/entities/measure"
import type { TopicLevel } from "@/shared/api"
import { useCatalogNames, useTranslation } from "@/shared/i18n"
import { staggerStyle } from "@/shared/motion"
import { IconLabel } from "@/shared/ui"
import { BlockButton } from "../block-button/block-button"
import styles from "./skill-panel.module.css"

export interface TopicRowProps {
  readonly topic: TopicLevel
  readonly index: number
  readonly widest: boolean
  readonly commonUncertainty: string
}

export function TopicRow({ topic, index, widest, commonUncertainty }: TopicRowProps) {
  const { t } = useTranslation("overview")
  const names = useCatalogNames()
  const words = useLevelWords()
  const uncertainty = words.uncertainty(topic.level.theta_sd)
  return (
    <li className={styles.row} style={staggerStyle(index)}>
      <div className={styles.rowHead}>
        <span className={styles.name}>{names.topic(topic.topic)}</span>
        <span className={styles.meta}>
          <span className={styles.band}>{words.band(topic.level.band)}</span>
          {uncertainty === commonUncertainty ? null : (
            <span className={styles.diff}>{uncertainty}</span>
          )}
          {widest ? (
            <IconLabel icon="uncertainty" tone="accent" className={styles.widest}>
              {t("skills.widest")}
            </IconLabel>
          ) : null}
        </span>
      </div>
      <GradeRuler level={topic.level} size="inline" caption={false} />
      <span className={styles.sources}>
        {topic.sources.map((source) => (
          <TrustBadge key={source} source={source} />
        ))}
      </span>
      <BlockButton topic={topic.topic.code} compact />
    </li>
  )
}
