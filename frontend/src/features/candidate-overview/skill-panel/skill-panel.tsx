import { useState } from "react"
import type { SkillProfile, TopicLevel } from "@/shared/api"
import { useTranslation } from "@/shared/i18n"
import { ButtonLink, Card, IconLabel, Segmented } from "@/shared/ui"
import styles from "./skill-panel.module.css"
import { TopicRow } from "./topic-row"

type SkillOrder = "catalog" | "weak"

const WIDEST_COUNT = 2

export interface SkillPanelProps {
  readonly profile: SkillProfile
  readonly fspLinked: boolean | null
  readonly motionIndex?: number
  readonly className?: string | undefined
}

function ordered(topics: readonly TopicLevel[], order: SkillOrder): readonly TopicLevel[] {
  if (order === "catalog") return topics
  return [...topics].sort((left, right) => left.level.theta - right.level.theta)
}

function widestTopics(topics: readonly TopicLevel[]): ReadonlySet<string> {
  const sorted = [...topics].sort((left, right) => right.level.theta_sd - left.level.theta_sd)
  return new Set(sorted.slice(0, WIDEST_COUNT).map((topic) => topic.topic.code))
}

export function SkillPanel({ profile, fspLinked, motionIndex, className }: SkillPanelProps) {
  const { t } = useTranslation("overview")
  const [order, setOrder] = useState<SkillOrder>("catalog")
  const widest = widestTopics(profile.topics)
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
      {fspLinked === false ? (
        <div className={styles.fsp}>
          <IconLabel icon="fsp" tone="secondary">
            {t("skills.noFsp")}
          </IconLabel>
          <ButtonLink to="/candidate/profile#fsp" variant="link" size="compact">
            {t("skills.linkFsp")}
          </ButtonLink>
        </div>
      ) : null}
      <ul className={styles.list} aria-label={t("skills.title")}>
        {ordered(profile.topics, order).map((topic, index) => (
          <TopicRow
            key={topic.topic.code}
            topic={topic}
            index={index}
            widest={widest.has(topic.topic.code)}
          />
        ))}
      </ul>
    </Card>
  )
}
