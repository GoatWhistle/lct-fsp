import type { CSSProperties } from "react"
import type { TopicLevel } from "@/shared/api"
import { useCatalogNames } from "@/shared/i18n"
import { GradeRuler } from "../grade-ruler/grade-ruler"
import { TrustBadge } from "../trust-badge/trust-badge"
import styles from "./skill-list.module.css"

export interface SkillListProps {
  readonly topics: readonly TopicLevel[]
  readonly label: string
  readonly animate?: boolean
}

export function SkillList({ topics, label, animate = false }: SkillListProps) {
  const names = useCatalogNames()
  return (
    <ul className={styles.list} aria-label={label}>
      {topics.map((topic, index) => (
        <li key={topic.topic.code} className={styles.row} style={{ "--i": index } as CSSProperties}>
          <div className={styles.head}>
            <span className={styles.name}>{names.topic(topic.topic)}</span>
            <span className={styles.sources}>
              {topic.sources.map((source) => (
                <TrustBadge key={source} source={source} />
              ))}
            </span>
          </div>
          <GradeRuler level={topic.level} size="inline" caption animate={animate} />
        </li>
      ))}
    </ul>
  )
}
