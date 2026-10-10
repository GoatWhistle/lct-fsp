import { useId, useState } from "react"
import { useGrades, useSpecializations } from "@/entities/catalog"
import { COMPANY_DIALOG_LINK } from "@/entities/company"
import { useSaveTask } from "@/entities/task"
import type { RegularTask, TaskKind } from "@/shared/api"
import { errorCodeOf, useCatalogNames, useErrorText, useTranslation } from "@/shared/i18n"
import {
  Banner,
  Button,
  ButtonLink,
  Combobox,
  Dialog,
  Form,
  Segmented,
  Select,
  TextArea,
  TextField,
  toast,
} from "@/shared/ui"
import { formOf, inputOf, MAX_TOPICS, type TaskForm, taskErrors } from "../task-form"
import styles from "./task-drawer.module.css"

const COMPANY_CODES = new Set(["company_required", "company_profile_required"])

export interface TaskDrawerProps {
  readonly open: boolean
  readonly task: RegularTask | null
  readonly onClose: () => void
}

export function TaskDrawer({ open, task, onClose }: TaskDrawerProps) {
  const { t } = useTranslation(["taskEditor", "common"])
  const names = useCatalogNames()
  const errorText = useErrorText()
  const formId = useId()
  const specializations = useSpecializations()
  const grades = useGrades()
  const save = useSaveTask()
  const [form, setForm] = useState<TaskForm>(() => formOf(task))
  const [tried, setTried] = useState(false)
  const failed = taskErrors(form)
  const show = (field: keyof typeof failed) =>
    tried && failed[field] ? t(`errors.${field}`) : undefined
  const patch = (next: Partial<TaskForm>) => setForm((current) => ({ ...current, ...next }))
  const topics = specializations.data?.find((item) => item.code === form.specialization)?.topics
  const submit = () => {
    setTried(true)
    const input = inputOf(form)
    if (input === null) return
    save.mutate(
      { id: task?.id ?? null, input },
      {
        onSuccess: () => {
          toast.success(t(task === null ? "toast.published" : "toast.saved"))
          onClose()
        },
      },
    )
  }
  const needsCompany = save.isError && COMPANY_CODES.has(errorCodeOf(save.error))
  return (
    <Dialog
      open={open}
      onClose={onClose}
      size="drawer"
      title={t(task === null ? "createTitle" : "editTitle")}
      description={t("drawerLead")}
      actions={
        <>
          <Button variant="ghost" onClick={onClose}>
            {t("common:action.cancel")}
          </Button>
          <Button
            type="submit"
            form={formId}
            icon={task === null ? "send" : "check"}
            pending={save.isPending}
            pendingLabel={t("saving")}
          >
            {t(task === null ? "publish" : "save")}
          </Button>
        </>
      }
    >
      <Form id={formId} onSubmit={submit} className={styles.form}>
        <div className={styles.pair}>
          <Select
            label={t("fields.specialization")}
            value={form.specialization}
            onChange={(specialization) => patch({ specialization, topics: [] })}
            options={(specializations.data ?? []).map((item) => ({
              value: item.code,
              label: names.specialization(item),
            }))}
            error={show("specialization")}
          />
          <Select
            label={t("fields.grade")}
            value={form.grade}
            onChange={(grade) => patch({ grade })}
            hint={t("fields.gradeHint")}
            options={[...(grades.data ?? [])]
              .sort((left, right) => left.rank - right.rank)
              .map((item) => ({ value: item.code, label: names.grade(item) }))}
            error={show("grade")}
          />
        </div>
        <Combobox
          label={t("fields.topics")}
          values={form.topics}
          onChange={(values) => patch({ topics: values })}
          max={MAX_TOPICS}
          disabled={topics === undefined}
          placeholder={topics === undefined ? t("fields.topicsFirst") : undefined}
          error={show("topics")}
          options={(topics ?? []).map((topic) => ({
            value: topic.code,
            label: names.topic(topic),
          }))}
        />
        <TextArea
          label={t("fields.prompt")}
          value={form.prompt}
          onChange={(prompt) => patch({ prompt })}
          maxLength={4000}
          minRows={6}
          error={show("prompt")}
        />
        <div className={styles.kind}>
          <Segmented<TaskKind>
            label={t("fields.kind")}
            showLabel
            value={form.kind}
            onChange={(kind) => patch({ kind })}
            options={[
              { value: "reference", label: t("kind.reference"), icon: "check" },
              { value: "open", label: t("kind.open"), icon: "edit" },
            ]}
          />
          <p className={styles.kindHint}>{t(`kindHint.${form.kind}`)}</p>
        </div>
        {form.kind === "reference" ? (
          <TextField
            label={t("fields.reference")}
            value={form.reference}
            onChange={(reference) => patch({ reference })}
            maxLength={200}
            error={show("reference")}
          />
        ) : null}
        {save.isError ? (
          <Banner
            tone="critical"
            title={errorText(save.error)}
            action={
              needsCompany ? (
                <ButtonLink to={COMPANY_DIALOG_LINK} size="compact" icon="company">
                  {t("toCompany")}
                </ButtonLink>
              ) : undefined
            }
          />
        ) : null}
      </Form>
    </Dialog>
  )
}
