import { useState } from "react"
import { useNavigate } from "react-router"
import { useSendInvitation } from "@/entities/invitation"
import type { InvitationBudget } from "@/shared/api"
import { useErrorText, useFormatters, useTranslation } from "@/shared/i18n"
import {
  Banner,
  Button,
  Dialog,
  Form,
  IconLabel,
  NumberField,
  TextArea,
  TextField,
  toast,
} from "@/shared/ui"
import styles from "./invite-dialog.module.css"

export interface InviteDefaults {
  readonly description: string
  readonly salaryFrom: number | null
  readonly salaryTo: number | null
}

export interface InviteDialogProps {
  readonly open: boolean
  readonly onClose: () => void
  readonly candidateId: string
  readonly label: string
  readonly defaults: InviteDefaults
  readonly budget: InvitationBudget | null
}

export function InviteDialog({
  open,
  onClose,
  candidateId,
  label,
  defaults,
  budget,
}: InviteDialogProps) {
  const { t } = useTranslation(["selection", "common"])
  const errorText = useErrorText()
  const format = useFormatters()
  const navigate = useNavigate()
  const send = useSendInvitation()
  const [description, setDescription] = useState(defaults.description)
  const [salaryFrom, setSalaryFrom] = useState(defaults.salaryFrom)
  const [salaryTo, setSalaryTo] = useState(defaults.salaryTo)
  const [contact, setContact] = useState("")
  const [touched, setTouched] = useState(false)
  const exhausted = budget !== null && budget.remaining <= 0
  const order = salaryFrom !== null && salaryTo !== null && salaryTo < salaryFrom
  const ready =
    description.trim() !== "" && salaryFrom !== null && salaryTo !== null && contact.trim() !== ""

  const submit = () => {
    setTouched(true)
    if (!ready || order || exhausted || salaryFrom === null || salaryTo === null) return
    send.mutate(
      {
        candidate_id: candidateId,
        description: description.trim(),
        salary_from: salaryFrom,
        salary_to: salaryTo,
        contact: contact.trim(),
      },
      {
        onSuccess: () => {
          onClose()
          toast.success(t("invite.sent"), {
            label: t("invite.open"),
            onAction: () => navigate("/employer/invitations"),
          })
        },
      },
    )
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={t("invite.title", { id: label })}
      size="regular"
      actions={
        <>
          <Button variant="ghost" onClick={onClose}>
            {t("common:action.cancel")}
          </Button>
          <Button
            icon="send"
            pending={send.isPending}
            pendingLabel={t("invite.sending")}
            disabled={exhausted}
            onClick={submit}
          >
            {t("invite.send")}
          </Button>
        </>
      }
    >
      <Form onSubmit={submit} className={styles.form}>
        {budget === null ? null : (
          <IconLabel
            icon="invitation"
            tone={exhausted ? "danger" : "secondary"}
            className={styles.budget}
          >
            {exhausted
              ? t("invite.budgetEmpty", { date: format.date(budget.resets_at) })
              : t("invite.budget", { remaining: budget.remaining, limit: budget.limit })}
          </IconLabel>
        )}
        <TextArea
          label={t("invite.description")}
          hint={t("invite.descriptionHint")}
          value={description}
          onChange={setDescription}
          minRows={4}
          maxLength={4000}
        />
        <fieldset className={styles.salary}>
          <legend className={styles.legend}>{t("invite.salary")}</legend>
          <NumberField
            label={t("common:money.fieldFrom")}
            value={salaryFrom}
            onChange={setSalaryFrom}
            min={0}
            step={10000}
          />
          <NumberField
            label={t("common:money.fieldTo")}
            value={salaryTo}
            onChange={setSalaryTo}
            min={0}
            step={10000}
            error={order ? t("invite.salaryOrder") : undefined}
          />
          <p className={styles.basis}>{t("common:money.basis")}</p>
        </fieldset>
        <TextField
          label={t("invite.contact")}
          hint={t("invite.contactHint")}
          value={contact}
          onChange={setContact}
          icon="email"
          maxLength={200}
        />
        {touched && !ready ? <Banner tone="attention" title={t("invite.required")} /> : null}
        {send.isError ? <Banner tone="critical" title={errorText(send.error)} /> : null}
      </Form>
    </Dialog>
  )
}
