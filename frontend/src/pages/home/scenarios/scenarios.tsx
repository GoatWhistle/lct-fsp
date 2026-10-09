import type { ReactNode } from "react"
import { GradeRuler, MatchScore } from "@/entities/measure"
import { useCatalogNames, useTranslation } from "@/shared/i18n"
import { Card, Icon, type IconName, Section } from "@/shared/ui"
import {
  SAMPLE_LEVEL,
  SAMPLE_SCORE,
  SAMPLE_STACK,
  SAMPLE_STACK_CAP,
  SAMPLE_TOPICS,
} from "../samples"
import styles from "./scenarios.module.css"

interface ScenarioProps {
  readonly title: string
  readonly points: readonly { readonly icon: IconName; readonly text: string }[]
  readonly sampleCaption: string
  readonly sample: ReactNode
}

function Scenario({ title, points, sampleCaption, sample }: ScenarioProps) {
  return (
    <Card as="article" level="section" title={title} className={styles.scenario}>
      <ul className={styles.points}>
        {points.map((point) => (
          <li key={point.text} className={styles.point}>
            <Icon name={point.icon} size="lg" className={styles.icon} />
            <span>{point.text}</span>
          </li>
        ))}
      </ul>
      <Card level="inner" as="div" className={styles.sample}>
        {sample}
        <p className={styles.caption}>{sampleCaption}</p>
      </Card>
    </Card>
  )
}

export function Scenarios() {
  const { t } = useTranslation("home")
  const names = useCatalogNames()
  return (
    <Section tone="card">
      <div className={styles.grid}>
        <Scenario
          title={t("candidate.title")}
          points={[
            { icon: "test", text: t("candidate.one") },
            { icon: "measure", text: t("candidate.two") },
            { icon: "lock", text: t("candidate.three") },
          ]}
          sampleCaption={`${t("candidate.sample")}: ${names.topic("backend.databases")}`}
          sample={<GradeRuler level={SAMPLE_LEVEL} animate />}
        />
        <Scenario
          title={t("employer.title")}
          points={[
            { icon: "need", text: t("employer.one") },
            { icon: "match", text: t("employer.two") },
            { icon: "invitation", text: t("employer.three") },
          ]}
          sampleCaption={t("employer.sample")}
          sample={
            <MatchScore
              score={SAMPLE_SCORE}
              topics={SAMPLE_TOPICS}
              stack={SAMPLE_STACK}
              stackCap={SAMPLE_STACK_CAP}
              acceptance={0.64}
              size="lg"
              animate
            />
          }
        />
      </div>
    </Section>
  )
}
