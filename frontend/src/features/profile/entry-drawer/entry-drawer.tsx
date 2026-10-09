import { useState } from "react"
import { useTechnologies } from "@/entities/catalog"
import { useTranslation } from "@/shared/i18n"
import { useLatched } from "@/shared/motion"
import { Button, Checkbox, Combobox, Dialog, TextArea, TextField } from "@/shared/ui"
import {
  type EntryErrors,
  type ExperienceDraft,
  LINE_MAX,
  STACK_MAX,
  SUMMARY_MAX,
  thisMonth,
  validateEntry,
} from "../experience"
import { MonthField } from "../month-field/month-field"
import styles from "./entry-drawer.module.css"

export interface EntryDrawerProps {
  readonly entry: ExperienceDraft | null
  readonly isNew: boolean
  readonly onSave: (entry: ExperienceDraft) => void
  readonly onClose: () => void
}

interface EntryFormProps {
  readonly initial: ExperienceDraft
  readonly onSave: (entry: ExperienceDraft) => void
}

const FORM_ID = "experience-entry-form"

function EntryForm({ initial, onSave }: EntryFormProps) {
  const { t } = useTranslation("profile")
  const technologies = useTechnologies()
  const [entry, setEntry] = useState(initial)
  const [errors, setErrors] = useState<EntryErrors>({})
  const patch = (next: Partial<ExperienceDraft>) => setEntry((current) => ({ ...current, ...next }))
  const current = entry.end === ""
  const message = (field: keyof EntryErrors) =>
    errors[field] === undefined
      ? undefined
      : t(`profile:experience.errors.${errors[field]}` as never)
  const submit = () => {
    const found = validateEntry(entry)
    setErrors(found)
    if (Object.keys(found).length === 0) onSave(entry)
  }
  return (
    <form
      id={FORM_ID}
      className={styles.form}
      noValidate
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
    >
      <TextField
        label={t("experience.place")}
        icon="company"
        value={entry.place}
        onChange={(place) => patch({ place })}
        maxLength={LINE_MAX}
        error={message("place")}
        required
      />
      <TextField
        label={t("experience.role")}
        value={entry.role}
        onChange={(role) => patch({ role })}
        maxLength={LINE_MAX}
      />
      <div className={styles.period}>
        <MonthField
          label={t("experience.start")}
          value={entry.start}
          onChange={(start) => patch({ start })}
          error={message("start")}
        />
        <MonthField
          label={t("experience.end")}
          value={entry.end}
          onChange={(end) => patch({ end })}
          error={message("end")}
          disabled={current}
        />
      </div>
      <Checkbox
        label={t("experience.current")}
        checked={current}
        onChange={(on) => patch({ end: on ? "" : thisMonth() })}
      />
      <Combobox
        label={t("experience.stack")}
        values={entry.stack}
        max={STACK_MAX}
        onChange={(stack) => patch({ stack })}
        options={(technologies.data ?? []).map((item) => ({ value: item.code, label: item.name }))}
        hint={t("experience.stackHint")}
      />
      <TextArea
        label={t("experience.summary")}
        value={entry.summary}
        onChange={(summary) => patch({ summary })}
        maxLength={SUMMARY_MAX}
        minRows={4}
        hint={t("experience.summaryHint")}
      />
    </form>
  )
}

export function EntryDrawer({ entry, isNew, onSave, onClose }: EntryDrawerProps) {
  const { t } = useTranslation("profile")
  const open = entry !== null
  const shown = useLatched(entry, open)
  const shownNew = useLatched(isNew, open)
  return (
    <Dialog
      open={open}
      onClose={onClose}
      size="drawer"
      title={shownNew ? t("experience.addTitle") : t("experience.editTitle")}
      description={t("experience.drawerLead")}
      actions={
        <>
          <Button variant="ghost" onClick={onClose}>
            {t("experience.cancel")}
          </Button>
          <Button type="submit" icon="check" form={FORM_ID}>
            {t("experience.apply")}
          </Button>
        </>
      }
    >
      {shown === null ? null : <EntryForm key={shown.key} initial={shown} onSave={onSave} />}
    </Dialog>
  )
}
