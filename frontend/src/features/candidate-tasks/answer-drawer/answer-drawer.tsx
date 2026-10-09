import { useState } from "react"
import { useAnswerTask } from "@/entities/task"
import type { CatalogTask } from "@/shared/api"
import {
  BackendText,
  useCatalogNames,
  useErrorText,
  useFormatters,
  useTranslation,
} from "@/shared/i18n"
import { useLatched } from "@/shared/motion"
import { Button, ConfirmDialog, Dialog, IconLabel, TextArea, toast } from "@/shared/ui"
import styles from "./answer-drawer.module.css"

const ANSWER_MAX = 4000

export interface AnswerDrawerProps {
  readonly task: CatalogTask | null
  readonly onClose: () => void
}

function AnswerForm({ task, onDone }: { readonly task: CatalogTask; readonly onDone: () => void }) {
  const { t } = useTranslation("tasks")
  const names = useCatalogNames()
  const format = useFormatters()
  const errorText = useErrorText()
  const answer = useAnswerTask()
  const [response, setResponse] = useState("")
  const [asking, setAsking] = useState(false)
  const empty = response.trim() === ""
  const send = () =>
    answer.mutate(
      { taskId: task.id, response: response.trim() },
      {
        onSuccess: (saved) => {
          setAsking(false)
          onDone()
          toast.success(t(`toast.${saved.status}`))
        },
        onError: (error) => {
          setAsking(false)
          toast.error(errorText(error))
        },
      },
    )
  return (
    <div className={styles.form}>
      <BackendText as="p" className={styles.prompt}>
        {task.prompt}
      </BackendText>
      <IconLabel icon="topic" tone="secondary" size="sm">
        {format.list(task.topics.map((topic) => names.topic(topic)))}
      </IconLabel>
      <TextArea
        label={t("answer.label")}
        value={response}
        onChange={setResponse}
        maxLength={ANSWER_MAX}
        minRows={task.kind === "open" ? 8 : 3}
        hint={t(`answer.hint.${task.kind}`)}
      />
      <IconLabel icon="info" tone="secondary" className={styles.note}>
        {t("answer.once")}
      </IconLabel>
      <div className={styles.actions}>
        <Button icon="send" disabled={empty} onClick={() => setAsking(true)}>
          {t("answer.send")}
        </Button>
      </div>
      <ConfirmDialog
        open={asking}
        title={t("answer.confirmTitle")}
        description={t(`answer.confirmText.${task.kind}`)}
        confirmLabel={t("answer.send")}
        pending={answer.isPending}
        onConfirm={send}
        onClose={() => setAsking(false)}
      />
    </div>
  )
}

export function AnswerDrawer({ task, onClose }: AnswerDrawerProps) {
  const { t } = useTranslation("tasks")
  const names = useCatalogNames()
  const open = task !== null
  const shown = useLatched(task, open)
  return (
    <Dialog
      open={open}
      onClose={onClose}
      size="drawer"
      title={t("answer.title")}
      description={
        shown === null
          ? undefined
          : t("answer.lead", { grade: names.grade(shown.grade), kind: t(`kind.${shown.kind}`) })
      }
    >
      {shown === null ? null : <AnswerForm key={shown.id} task={shown} onDone={onClose} />}
    </Dialog>
  )
}
