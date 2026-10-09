import type { CSSProperties } from "react"
import type { StackFit, TopicFit } from "@/shared/api"
import { useCatalogNames, useFormatters, useTranslation } from "@/shared/i18n"
import { useLevelWords } from "../use-level-words"
import styles from "./match-score.module.css"

export type MatchScoreSize = "lg" | "md" | "sm"

export interface MatchScoreProps {
  readonly score: number
  readonly topics: readonly TopicFit[]
  readonly stack?: StackFit | null | undefined
  readonly stackCap: number
  readonly acceptance?: number | null | undefined
  readonly size?: MatchScoreSize
  readonly animate?: boolean
}

function slotStyle(grow: number, fill: number, index: number): CSSProperties {
  return { flexGrow: grow, "--fill": fill, "--i": index } as CSSProperties
}

export function MatchScore({
  score,
  topics,
  stack,
  stackCap,
  acceptance,
  size = "md",
  animate = false,
}: MatchScoreProps) {
  const { t } = useTranslation("measure")
  const names = useCatalogNames()
  const words = useLevelWords()
  const format = useFormatters()
  const value = format.percent(score)
  const topicWeight = 1 - stackCap
  const summary = [
    t("match.aria", { value }),
    ...topics.map((topic) =>
      t("match.segment", {
        topic: names.topic(topic.topic),
        value: words.probability(topic.probability),
      }),
    ),
  ].join(". ")

  return (
    <div className={styles.match} data-size={size} data-animate={animate}>
      <div className={styles.figure}>
        <span className={styles.value}>{value}</span>
        <span className={size === "sm" ? "visually-hidden" : styles.label}>{t("match.label")}</span>
      </div>
      <div className={styles.bar} role="img" aria-label={summary}>
        {topics.map((topic, index) => (
          <span
            key={topic.topic.code}
            className={styles.slot}
            style={slotStyle(topic.weight * topicWeight, topic.probability, index)}
            title={t("match.segment", {
              topic: names.topic(topic.topic),
              value: words.probability(topic.probability),
            })}
          >
            <span className={styles.fill} data-importance={topic.importance} />
          </span>
        ))}
        {stack === undefined || stack === null || stackCap <= 0 ? null : (
          <span
            className={styles.slot}
            style={slotStyle(stackCap, stack.overlap, topics.length)}
            title={t("match.stack", { value: format.percent(stack.overlap) })}
          >
            <span className={styles.fill} data-importance="self" />
          </span>
        )}
      </div>
      {acceptance === undefined || acceptance === null ? null : (
        <span className={styles.label}>
          {t("match.acceptance", { value: words.probability(acceptance) })}
        </span>
      )}
    </div>
  )
}
