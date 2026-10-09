import type { CSSProperties } from "react"
import type { GradeProbability } from "@/shared/api"
import { useCatalogNames } from "@/shared/i18n"
import { useLevelWords } from "../use-level-words"
import styles from "./grade-probabilities.module.css"

export interface GradeProbabilitiesProps {
  readonly items: readonly GradeProbability[]
  readonly highlight?: string | null | undefined
  readonly label: string
  readonly animate?: boolean
}

export function GradeProbabilities({
  items,
  highlight,
  label,
  animate = false,
}: GradeProbabilitiesProps) {
  const names = useCatalogNames()
  const words = useLevelWords()
  return (
    <dl className={styles.list} aria-label={label} data-animate={animate}>
      {items.map((item, index) => (
        <div
          key={item.grade}
          className={styles.row}
          data-highlight={item.grade === highlight}
          style={{ "--i": index, "--fill": item.probability } as CSSProperties}
        >
          <dt className={styles.grade}>{names.grade(item.grade)}</dt>
          <dd className={styles.bar} aria-hidden="true">
            <span className={styles.fill} />
          </dd>
          <dd className={styles.value}>{words.probability(item.probability)}</dd>
        </div>
      ))}
    </dl>
  )
}
