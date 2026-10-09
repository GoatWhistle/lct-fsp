import { useId, useState } from "react"
import { useGrades, useSpecializations } from "@/entities/catalog"
import { useSaveVacancy } from "@/entities/vacancy"
import type { Vacancy, WorkFormat } from "@/shared/api"
import { errorCodeOf, useCatalogNames, useErrorText, useTranslation } from "@/shared/i18n"
import {
  Banner,
  Button,
  ButtonLink,
  Dialog,
  Form,
  Select,
  TextArea,
  TextField,
  toast,
} from "@/shared/ui"
import { formOf, inputOf, toggleFormat, type VacancyForm, vacancyErrors } from "../vacancy-form"
import { FormatTiles } from "./format-tiles"
import { SalaryFields } from "./salary-fields"
import styles from "./vacancy-drawer.module.css"

const COMPANY_CODES = new Set(["company_required", "company_profile_required"])

export interface VacancyDrawerProps {
  readonly open: boolean
  readonly vacancy: Vacancy | null
  readonly onClose: () => void
}

export function VacancyDrawer({ open, vacancy, onClose }: VacancyDrawerProps) {
  const { t } = useTranslation(["vacancyEditor", "common"])
  const names = useCatalogNames()
  const errorText = useErrorText()
  const formId = useId()
  const specializations = useSpecializations()
  const grades = useGrades()
  const save = useSaveVacancy()
  const [form, setForm] = useState<VacancyForm>(() => formOf(vacancy))
  const [tried, setTried] = useState(false)
  const failed = vacancyErrors(form)
  const show = (field: keyof typeof failed) =>
    tried && failed[field] ? t(`errors.${field}`) : undefined
  const patch = (next: Partial<VacancyForm>) => setForm((current) => ({ ...current, ...next }))
  const submit = () => {
    setTried(true)
    const input = inputOf(form)
    if (input === null) return
    save.mutate(
      { id: vacancy?.id ?? null, input },
      {
        onSuccess: () => {
          toast.success(t(vacancy === null ? "toast.published" : "toast.saved"))
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
      title={t(vacancy === null ? "createTitle" : "editTitle")}
      description={t("drawerLead")}
      actions={
        <>
          <Button variant="ghost" onClick={onClose}>
            {t("common:action.cancel")}
          </Button>
          <Button
            type="submit"
            form={formId}
            icon={vacancy === null ? "send" : "check"}
            pending={save.isPending}
            pendingLabel={t("saving")}
          >
            {t(vacancy === null ? "publish" : "save")}
          </Button>
        </>
      }
    >
      <Form id={formId} onSubmit={submit} className={styles.form}>
        <TextField
          label={t("fields.title")}
          value={form.title}
          onChange={(title) => patch({ title })}
          maxLength={200}
          placeholder={t("fields.titlePlaceholder")}
          error={show("title")}
        />
        <div className={styles.pair}>
          <Select
            label={t("fields.specialization")}
            value={form.specialization}
            onChange={(specialization) => patch({ specialization })}
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
            options={[...(grades.data ?? [])]
              .sort((left, right) => left.rank - right.rank)
              .map((item) => ({ value: item.code, label: names.grade(item) }))}
            error={show("grade")}
          />
        </div>
        <FormatTiles
          selected={form.formats}
          onToggle={(format: WorkFormat) => patch({ formats: toggleFormat(form.formats, format) })}
          error={show("formats")}
        />
        <SalaryFields
          from={form.salaryFrom}
          to={form.salaryTo}
          onChange={(salaryFrom, salaryTo) => patch({ salaryFrom, salaryTo })}
          error={show("salary")}
        />
        <TextArea
          label={t("fields.description")}
          value={form.description}
          onChange={(description) => patch({ description })}
          maxLength={5000}
          minRows={6}
          hint={t("fields.descriptionHint")}
        />
        {save.isError ? (
          <Banner
            tone="critical"
            title={errorText(save.error)}
            action={
              needsCompany ? (
                <ButtonLink to="/employer/company" size="compact" icon="company">
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
