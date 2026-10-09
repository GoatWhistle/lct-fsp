import { useState } from "react"
import { useGradeAnswer } from "@/entities/task"
import type { AuthorAnswer, RegularTask } from "@/shared/api"
import { BackendText, useErrorText, useFormatters, useTranslation } from "@/shared/i18n"
import { Button, ConfirmDialog, RadioGroup, StatusBadge, toast } from "@/shared/ui"
import { RUBRIC, type RubricScore } from "../task-form"
import styles from "./answer-row.module.css"

export interface AnswerRowProps {
  readonly task: RegularTask
  readonly answer: AuthorAnswer
}

function Verdict({ task, answer }: AnswerRowProps) {
  const { t } = useTranslation("taskEditor")
  if (task.kind === "reference")
    return answer.correct === true ? (
      <StatusBadge tone="positive" icon="accepted">
        {t("answers.correct")}
      </StatusBadge>
    ) : (
      <StatusBadge tone="neutral" icon="declined">
        {t("answers.incorrect")}
      </StatusBadge>
    )
  if (answer.rubric === null)
    return (
      <StatusBadge tone="attention" icon="pending">
        {t("answers.awaiting")}
      </StatusBadge>
    )
  return (
    <StatusBadge tone="positive" icon="accepted" swapKey={String(answer.rubric)}>
      {t("answers.graded", { score: answer.rubric, max: RUBRIC.length - 1 })}
    </StatusBadge>
  )
}

function GradeForm({ task, answer }: AnswerRowProps) {
  const { t } = useTranslation("taskEditor")
  const errorText = useErrorText()
  const grade = useGradeAnswer(task.id)
  const [score, setScore] = useState<RubricScore | null>(null)
  const [asking, setAsking] = useState(false)
  const confirm = () => {
    if (score === null) return
    grade.mutate(
      { answerId: answer.id, rubric: score },
      {
        onSuccess: () => {
          setAsking(false)
          toast.success(t("grade.done"))
        },
        onError: (error) => {
          setAsking(false)
          toast.error(errorText(error))
        },
      },
    )
  }
  return (
    <div className={styles.grade}>
      <RadioGroup<`${RubricScore}`>
        label={t("grade.label")}
        appearance="card"
        className={styles.scale}
        value={score === null ? null : `${score}`}
        onChange={(value) => setScore(Number(value) as RubricScore)}
        options={RUBRIC.map((value) => ({
          value: `${value}` as const,
          label: t("grade.score", { score: value }),
          hint: t(`rubric.${value}`),
        }))}
      />
      <div>
        <Button icon="check" disabled={score === null} onClick={() => setAsking(true)}>
          {t("grade.action")}
        </Button>
      </div>
      <ConfirmDialog
        open={asking}
        title={t("grade.confirmTitle", { score: score ?? 0, max: RUBRIC.length - 1 })}
        description={t("grade.confirmText")}
        confirmLabel={t("grade.confirmAction")}
        pending={grade.isPending}
        onConfirm={confirm}
        onClose={() => setAsking(false)}
      />
    </div>
  )
}

function pseudonymTag(label: string): string {
  return `#${label.split(" ").at(-1) ?? label}`
}

export function AnswerRow({ task, answer }: AnswerRowProps) {
  const { t } = useTranslation("taskEditor")
  const format = useFormatters()
  const gradable = task.kind === "open" && answer.rubric === null && task.withdrawn_at === null
  return (
    <li className={styles.row}>
      <header className={styles.head}>
        <span className={styles.who}>{pseudonymTag(answer.candidate)}</span>
        <span className={styles.when}>{format.dateTime(answer.answered_at)}</span>
        <Verdict task={task} answer={answer} />
      </header>
      <BackendText as="p" className={styles.response}>
        {answer.response}
      </BackendText>
      {answer.rubric === null ? null : (
        <p className={styles.rubric}>{t(`rubric.${answer.rubric as RubricScore}`)}</p>
      )}
      {gradable ? <GradeForm task={task} answer={answer} /> : null}
    </li>
  )
}
