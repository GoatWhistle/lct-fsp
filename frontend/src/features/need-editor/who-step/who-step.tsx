import { gradeIcon, specializationIcon, useGrades, useSpecializations } from "@/entities/catalog"
import { useCatalogNames, useTranslation } from "@/shared/i18n"
import { ChoiceTiles, IconLabel, Skeleton, TextArea, TextField } from "@/shared/ui"
import type { NeedErrors, NeedForm } from "../need-form"
import styles from "./who-step.module.css"

export interface WhoStepProps {
  readonly form: NeedForm
  readonly errors: NeedErrors
  readonly uncertain: ReadonlySet<string>
  readonly onChange: (patch: Partial<NeedForm>) => void
}

function FieldError({ text }: { readonly text: string | undefined }) {
  if (text === undefined) return null
  return (
    <IconLabel icon="critical" tone="danger" className={styles.error}>
      {text}
    </IconLabel>
  )
}

export function WhoStep({ form, errors, uncertain, onChange }: WhoStepProps) {
  const { t } = useTranslation("need")
  const names = useCatalogNames()
  const specializations = useSpecializations()
  const grades = useGrades()
  const flag = (field: string) => (uncertain.has(field) ? t("text.uncertain") : undefined)
  const error = (key: keyof NeedErrors) =>
    errors[key] === undefined ? undefined : t(`need:errors.${errors[key]}` as never)

  return (
    <div className={styles.step}>
      <TextField
        label={t("who.title")}
        value={form.title}
        onChange={(title) => onChange({ title })}
        placeholder={t("who.titlePlaceholder")}
        maxLength={200}
        error={error("title")}
      />
      <TextArea
        label={t("who.team")}
        value={form.team}
        onChange={(team) => onChange({ team })}
        placeholder={t("who.teamPlaceholder")}
        hint={t("who.teamHint")}
        minRows={3}
      />
      {specializations.data === undefined || grades.data === undefined ? (
        <Skeleton shape="block" />
      ) : (
        <>
          <ChoiceTiles
            legend={t("who.specialization")}
            layout="inline"
            value={form.specialization}
            onChange={(specialization) => onChange({ specialization, stack: [], importance: {} })}
            tiles={specializations.data.map((item) => ({
              value: item.code,
              title: names.specialization(item),
              icon: specializationIcon(item.code),
              badge: item.code === form.specialization ? flag("specialization") : undefined,
            }))}
          />
          <FieldError text={error("specialization")} />
          <ChoiceTiles
            legend={t("who.grade")}
            columns="compact"
            layout="inline"
            value={form.grade}
            onChange={(grade) => onChange({ grade })}
            tiles={grades.data.map((item) => ({
              value: item.code,
              title: names.grade(item),
              icon: gradeIcon(item.code),
              badge: item.code === form.grade ? flag("grade") : undefined,
            }))}
          />
          <FieldError text={error("grade")} />
        </>
      )}
    </div>
  )
}
