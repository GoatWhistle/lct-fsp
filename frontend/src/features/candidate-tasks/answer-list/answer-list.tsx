import { gradeIcon } from "@/entities/catalog"
import { useMyAnswers } from "@/entities/task"
import type { AnswerStatus, OwnAnswer } from "@/shared/api"
import { BackendText, useCatalogNames, useFormatters, useTranslation } from "@/shared/i18n"
import { staggerStyle } from "@/shared/motion"
import {
  ButtonLink,
  Card,
  Chip,
  EmptyState,
  IconLabel,
  type IconName,
  LoadError,
  Skeleton,
  StatusBadge,
  type StatusTone,
} from "@/shared/ui"
import styles from "./answer-list.module.css"

const TONE: Readonly<Record<AnswerStatus, StatusTone>> = {
  accepted: "positive",
  awaiting_review: "progress",
  reviewed: "positive",
}

const ICON: Readonly<Record<AnswerStatus, IconName>> = {
  accepted: "accepted",
  awaiting_review: "pending",
  reviewed: "check",
}

function AnswerRow({ answer, index }: { readonly answer: OwnAnswer; readonly index: number }) {
  const { t } = useTranslation("tasks")
  const names = useCatalogNames()
  const format = useFormatters()
  return (
    <li className={styles.row} style={staggerStyle(index)}>
      <div className={styles.head}>
        <span className={styles.tags}>
          <Chip icon={gradeIcon(answer.task.grade.code)}>{names.grade(answer.task.grade)}</Chip>
          <IconLabel icon="calendar" tone="secondary" size="sm" className={styles.date}>
            {t("answers.answered", { date: format.date(answer.answered_at) })}
          </IconLabel>
        </span>
        <StatusBadge tone={TONE[answer.status]} icon={ICON[answer.status]} swapKey={answer.status}>
          {t(`status.${answer.status}`)}
        </StatusBadge>
      </div>
      <BackendText as="p" className={styles.prompt}>
        {answer.task.prompt}
      </BackendText>
      <div className={styles.response}>
        <span className={styles.label}>{t("answers.yours")}</span>
        <BackendText as="p" className={styles.text}>
          {answer.response}
        </BackendText>
      </div>
      <p className={styles.explain}>{t(`statusHint.${answer.status}`)}</p>
    </li>
  )
}

export function AnswerList() {
  const { t } = useTranslation("tasks")
  const answers = useMyAnswers()
  if (answers.isError)
    return (
      <LoadError
        error={answers.error}
        onRetry={() => void answers.refetch()}
        pending={answers.isFetching}
      />
    )
  if (answers.data === undefined) return <Skeleton shape="block" />
  if (answers.data.length === 0)
    return (
      <EmptyState
        size="hero"
        icon="task"
        title={t("answers.emptyTitle")}
        description={t("answers.emptyText")}
        action={
          <ButtonLink to="/candidate/tasks" icon="task">
            {t("answers.toTasks")}
          </ButtonLink>
        }
      />
    )
  return (
    <Card title={t("answers.title")} description={t("answers.lead")}>
      <ul className={styles.list}>
        {answers.data.map((answer, index) => (
          <AnswerRow key={answer.task.id} answer={answer} index={index} />
        ))}
      </ul>
    </Card>
  )
}
