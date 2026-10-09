import { useState } from "react"
import { gradeIcon, specializationIcon } from "@/entities/catalog"
import { useTaskAnswers, useWithdrawTask } from "@/entities/task"
import type { RegularTask } from "@/shared/api"
import {
  BackendText,
  useCatalogNames,
  useErrorText,
  useFormatters,
  useTranslation,
} from "@/shared/i18n"
import {
  Card,
  Chip,
  ConfirmDialog,
  Disclosure,
  EmptyState,
  IconLabel,
  LoadError,
  Menu,
  type MenuItem,
  Skeleton,
  StatusBadge,
  toast,
} from "@/shared/ui"
import { AnswerRow } from "../answer-row/answer-row"
import styles from "./task-card.module.css"

export interface TaskCardProps {
  readonly task: RegularTask
  readonly awaiting: boolean
  readonly index: number
  readonly onEdit: (task: RegularTask) => void
}

function Answers({ task }: { readonly task: RegularTask }) {
  const { t } = useTranslation("taskEditor")
  const answers = useTaskAnswers(task.id, task.answers > 0)
  if (task.answers === 0)
    return (
      <EmptyState
        icon="task"
        title={t("answers.emptyTitle")}
        description={t("answers.emptyText")}
      />
    )
  if (answers.isError)
    return (
      <LoadError
        error={answers.error}
        onRetry={() => void answers.refetch()}
        pending={answers.isFetching}
      />
    )
  if (answers.data === undefined) return <Skeleton lines={3} />
  return (
    <ul className={styles.answers}>
      {answers.data.map((answer) => (
        <AnswerRow key={answer.id} task={task} answer={answer} />
      ))}
    </ul>
  )
}

export function TaskCard({ task, awaiting, index, onEdit }: TaskCardProps) {
  const { t } = useTranslation(["taskEditor", "common"])
  const names = useCatalogNames()
  const format = useFormatters()
  const errorText = useErrorText()
  const withdraw = useWithdrawTask()
  const [asking, setAsking] = useState(false)
  const withdrawn = task.withdrawn_at !== null
  const items: MenuItem[] = [
    ...(task.editable
      ? [{ id: "edit", label: t("card.edit"), icon: "edit" as const, onSelect: () => onEdit(task) }]
      : []),
    { id: "withdraw", label: t("card.withdraw"), icon: "revoked", onSelect: () => setAsking(true) },
  ]
  const confirmWithdraw = () =>
    withdraw.mutate(task.id, {
      onSuccess: () => {
        setAsking(false)
        toast.success(t("toast.withdrawn"))
      },
      onError: (error) => {
        setAsking(false)
        toast.error(errorText(error))
      },
    })
  return (
    <Card
      as="article"
      motionIndex={index}
      data-withdrawn={withdrawn}
      className={styles.card}
      title={task.topics.map((topic) => names.topic(topic)).join(", ")}
      description={t("card.created", { date: format.date(task.created_at) })}
      actions={
        withdrawn ? undefined : (
          <Menu
            label={t("common:action.more")}
            icon="more"
            placement="bottom-end"
            items={items}
            iconOnly
          />
        )
      }
    >
      <div className={styles.tags}>
        <Chip icon={specializationIcon(task.specialization.code)} tone="accent">
          {names.specialization(task.specialization)}
        </Chip>
        <Chip icon={gradeIcon(task.grade.code)} tone="accent">
          {names.grade(task.grade)}
        </Chip>
        <StatusBadge tone="neutral" icon={task.kind === "reference" ? "check" : "edit"}>
          {t(`kind.${task.kind}`)}
        </StatusBadge>
        {withdrawn ? (
          <StatusBadge tone="neutral" icon="revoked">
            {t("card.withdrawnAt", { date: format.date(task.withdrawn_at ?? task.updated_at) })}
          </StatusBadge>
        ) : null}
        {awaiting ? (
          <StatusBadge tone="attention" icon="pending">
            {t("card.awaiting")}
          </StatusBadge>
        ) : null}
      </div>
      <BackendText as="p" className={styles.prompt}>
        {task.prompt}
      </BackendText>
      {task.reference_answer === null ? null : (
        <IconLabel icon="key" tone="secondary">
          {t("card.reference", { answer: task.reference_answer })}
        </IconLabel>
      )}
      <Disclosure summary={t("card.answers", { count: task.answers })} defaultOpen={awaiting}>
        <Answers task={task} />
      </Disclosure>
      <ConfirmDialog
        open={asking}
        title={t("withdraw.title")}
        description={t("withdraw.text")}
        confirmLabel={t("withdraw.action")}
        tone="danger"
        pending={withdraw.isPending}
        onConfirm={confirmWithdraw}
        onClose={() => setAsking(false)}
      />
    </Card>
  )
}
