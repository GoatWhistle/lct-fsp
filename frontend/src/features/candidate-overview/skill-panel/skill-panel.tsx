import { useState } from "react"
import { useLevelWords } from "@/entities/measure"
import type { SkillProfile, TopicLevel } from "@/shared/api"
import { useTranslation } from "@/shared/i18n"
import { Card, Segmented } from "@/shared/ui"
import styles from "./skill-panel.module.css"
import { TopicRow } from "./topic-row"

type SkillOrder = "catalog" | "weak"

const WIDEST_COUNT = 2

export interface SkillPanelProps {
  readonly profile: SkillProfile
  readonly motionIndex?: number
  readonly className?: string | undefined
}

function ordered(topics: readonly TopicLevel[], order: SkillOrder): readonly TopicLevel[] {
  if (order === "catalog") return topics
  return [...topics].sort((left, right) => left.level.theta - right.level.theta)
}

function commonUncertainty(topics: readonly TopicLevel[], word: (sd: number) => string): string {
  const counts = new Map<string, number>()
  for (const topic of topics) {
    const key = word(topic.level.theta_sd)
    counts.set(key, (counts.get(key) ?? 0) + 1)
  }
  return [...counts.entries()].sort((left, right) => right[1] - left[1])[0]?.[0] ?? ""
}

function widestTopics(topics: readonly TopicLevel[]): ReadonlySet<string> {
  const sorted = [...topics].sort((left, right) => right.level.theta_sd - left.level.theta_sd)
  return new Set(sorted.slice(0, WIDEST_COUNT).map((topic) => topic.topic.code))
}

export function SkillPanel({ profile, motionIndex, className }: SkillPanelProps) {
  const { t } = useTranslation("overview")
  const [order, setOrder] = useState<SkillOrder>("catalog")
  const words = useLevelWords()
  const widest = widestTopics(profile.topics)
  const common = commonUncertainty(profile.topics, words.uncertainty)
  return (
    <Card
      title={t("skills.title")}
      description={t("skills.lead")}
      motionIndex={motionIndex}
      className={className}
      actions={
        <Segmented
          label={t("skills.order")}
          size="compact"
          value={order}
          onChange={setOrder}
          options={[
            { value: "catalog", label: t("skills.byCatalog"), icon: "topic" },
            { value: "weak", label: t("skills.weakFirst"), icon: "sort" },
          ]}
        />
      }
    >
      {common === "" ? null : (
        <p className={styles.common}>{t("skills.common", { value: common })}</p>
      )}
      <ul className={styles.list} aria-label={t("skills.title")}>
        {ordered(profile.topics, order).map((topic, index) => (
          <TopicRow
            key={topic.topic.code}
            topic={topic}
            index={index}
            widest={widest.has(topic.topic.code)}
            commonUncertainty={common}
          />
        ))}
      </ul>
    </Card>
  )
}
