import type { ReactNode } from "react"
import { MatchScore } from "@/entities/measure"
import { anonymousId } from "@/entities/selection"
import type { SelectionEntry } from "@/shared/api"
import { useFormatters, useTranslation } from "@/shared/i18n"
import { Swap } from "@/shared/motion"
import { ButtonLink, Card, Chip, CloseButton, EmptyState, IconLabel, ScrollArea } from "@/shared/ui"
import { TopicFitRow } from "../topic-fit-row/topic-fit-row"
import styles from "./explanation-panel.module.css"

export interface ExplanationPanelProps {
  readonly entry: SelectionEntry | null
  readonly stackCap: number
  readonly invite: ReactNode
  readonly onClose: () => void
  readonly framed?: boolean
}

function StackPart({ entry, stackCap }: { entry: SelectionEntry; stackCap: number }) {
  const { t } = useTranslation("selection")
  const format = useFormatters()
  const { stack } = entry
  return (
    <section className={styles.section} aria-label={t("explain.stack")}>
      <p className={styles.subtitle}>{t("explain.stack")}</p>
      {stack.contribution === null ? (
        <p className={styles.muted}>{t("explain.stackNone")}</p>
      ) : (
        <>
          <span className={styles.chips}>
            {stack.matched.map((tech) => (
              <Chip key={tech.code}>{tech.name}</Chip>
            ))}
          </span>
          <span className={styles.stackFacts}>
            <IconLabel icon="self-report" tone="secondary">
              {t("explain.stackMatched", { matched: stack.matched.length, total: stack.total })}
            </IconLabel>
            <span className={styles.mono}>
              {t("explain.stackCap", {
                value: format.percent(stack.contribution, 1),
                cap: format.percent(stackCap),
              })}
            </span>
          </span>
        </>
      )}
    </section>
  )
}

function Explanation({
  entry,
  stackCap,
  invite,
}: {
  readonly entry: SelectionEntry
  readonly stackCap: number
  readonly invite: ReactNode
}) {
  const { t } = useTranslation("selection")
  return (
    <Swap swapKey={entry.candidate_id} as="div" className={styles.body}>
      {entry.match_score === null ? (
        <p className={styles.muted}>{t("explain.unconfirmed")}</p>
      ) : (
        <>
          <MatchScore
            score={entry.match_score}
            topics={entry.topics}
            stack={entry.stack}
            stackCap={stackCap}
            acceptance={entry.acceptance_probability}
            size="lg"
            animate
          />
          <p className={styles.muted}>{t("explain.place")}</p>
        </>
      )}
      <section className={styles.section} aria-label={t("explain.topics")}>
        <p className={styles.subtitle}>{t("explain.topics")}</p>
        <ul className={styles.topics}>
          {entry.topics.map((topic, index) => (
            <TopicFitRow key={topic.topic.code} topic={topic} index={index} />
          ))}
        </ul>
      </section>
      <StackPart entry={entry} stackCap={stackCap} />
      <div className={styles.actions}>
        {invite}
        <ButtonLink
          to={`/employer/candidates/${entry.candidate_id}`}
          variant="secondary"
          size="compact"
          icon="profile"
        >
          {t("explain.card")}
        </ButtonLink>
      </div>
    </Swap>
  )
}

export function ExplanationPanel({
  entry,
  stackCap,
  invite,
  onClose,
  framed = true,
}: ExplanationPanelProps) {
  const { t } = useTranslation("selection")
  if (entry !== null && !framed)
    return <Explanation entry={entry} stackCap={stackCap} invite={invite} />
  if (entry === null)
    return (
      <Card as="aside" level="inner" className={styles.panel}>
        <EmptyState icon="match" title={t("explain.emptyTitle")} description={t("explain.empty")} />
      </Card>
    )
  const id = anonymousId(entry.candidate_id)
  return (
    <Card
      as="aside"
      className={styles.panel}
      title={
        <span className={styles.title}>
          <span>{t("explain.title")}</span>
          <span className={styles.id}>{id}</span>
        </span>
      }
      actions={<CloseButton label={t("explain.close")} onClick={onClose} />}
    >
      <ScrollArea className={styles.scroll}>
        <Explanation entry={entry} stackCap={stackCap} invite={invite} />
      </ScrollArea>
    </Card>
  )
}
