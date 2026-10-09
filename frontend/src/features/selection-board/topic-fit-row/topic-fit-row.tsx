import { GradeRuler, TrustBadge, VerdictMark } from "@/entities/measure"
import type { TopicFit } from "@/shared/api"
import { useCatalogNames, useFormatters, useTranslation } from "@/shared/i18n"
import { staggerStyle } from "@/shared/motion"
import { Chip } from "@/shared/ui"
import { levelOf } from "../selection-model"
import styles from "./topic-fit-row.module.css"

export interface TopicFitRowProps {
  readonly topic: TopicFit
  readonly index: number
}

export function TopicFitRow({ topic, index }: TopicFitRowProps) {
  const { t } = useTranslation(["selection", "catalog"])
  const names = useCatalogNames()
  const format = useFormatters()
  return (
    <li className={styles.row} style={staggerStyle(index)}>
      <div className={styles.head}>
        <span className={styles.name}>{names.topic(topic.topic)}</span>
        <Chip tone={topic.importance === "key" ? "accent" : "neutral"}>
          {t(`catalog:importance.${topic.importance}` as never)}
        </Chip>
        <span className={styles.weight}>
          {t("explain.weight", { value: format.percent(topic.weight) })}
        </span>
      </div>
      <GradeRuler
        level={levelOf(topic)}
        size="inline"
        required={topic.requirement}
        caption={false}
        animate
      />
      <div className={styles.foot}>
        <VerdictMark verdict={topic.verdict} lowData={topic.low_data} />
        <span className={styles.contribution}>
          {t("explain.contribution")} <strong>{format.percent(topic.contribution, 1)}</strong>
        </span>
        {topic.fsp_confirmed ? <TrustBadge source="fsp" /> : null}
        {topic.verification_confirmed ? <TrustBadge source="verification" /> : null}
        {topic.regular_task ? <TrustBadge source="regular_task" /> : null}
      </div>
    </li>
  )
}
