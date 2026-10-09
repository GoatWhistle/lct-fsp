import { type ChangeEvent, type DragEvent, useState } from "react"
import { useParseResume } from "@/entities/profile"
import type { ResumeDraft } from "@/shared/api"
import { useCatalogNames, useErrorText, useTranslation } from "@/shared/i18n"
import { Swap } from "@/shared/motion"
import { Banner, Disclosure, Icon, IconLabel } from "@/shared/ui"
import { EditorSection } from "../editor-section/editor-section"
import { recognizedFields } from "../profile-draft"
import styles from "./resume-drop.module.css"

const PDF_TYPE = "application/pdf"

export interface ResumeDropProps {
  readonly onParsed: (parsed: ResumeDraft) => void
  readonly parsed: ResumeDraft | null
}

function Summary({ parsed }: { readonly parsed: ResumeDraft }) {
  const { t } = useTranslation("profile")
  const names = useCatalogNames()
  const fields = recognizedFields(parsed)
  return (
    <Banner
      tone="info"
      icon="file"
      title={t("resume.done", { count: fields.length })}
      className={styles.summary}
    >
      <Disclosure summary={t("resume.details")}>
        <ul className={styles.fields}>
          {fields.map((field) => (
            <li key={field}>
              <IconLabel
                icon={parsed.uncertain.includes(field) ? "alert" : "check"}
                tone={parsed.uncertain.includes(field) ? "danger" : "accent"}
              >
                {t(`resumeField.${field}`)}
              </IconLabel>
            </li>
          ))}
        </ul>
        {parsed.grade_hint === null ? null : (
          <p className={styles.hint}>
            {t("resume.gradeHint", { grade: names.grade(parsed.grade_hint.grade) })}
          </p>
        )}
      </Disclosure>
    </Banner>
  )
}

export function ResumeDrop({ onParsed, parsed }: ResumeDropProps) {
  const { t } = useTranslation("profile")
  const errorText = useErrorText()
  const parse = useParseResume()
  const [dragging, setDragging] = useState(false)

  const take = (file: File | undefined) => {
    if (file === undefined) return
    parse.mutate(file, { onSuccess: onParsed })
  }
  const onInput = (event: ChangeEvent<HTMLInputElement>) => {
    take(event.target.files?.[0])
    event.target.value = ""
  }
  const onDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault()
    setDragging(false)
    take(Array.from(event.dataTransfer.files).find((file) => file.type === PDF_TYPE))
  }
  const onDragOver = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault()
    setDragging(true)
  }
  const stage = parse.isPending ? "reading" : "idle"

  return (
    <EditorSection id="resume" title={t("sections.resume")} description={t("resume.lead")}>
      <label
        className={styles.zone}
        data-dragging={dragging}
        data-busy={parse.isPending}
        onDragOver={onDragOver}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <input
          type="file"
          accept={PDF_TYPE}
          className="visually-hidden"
          disabled={parse.isPending}
          onChange={onInput}
        />
        <Icon
          name={parse.isPending ? "loader" : "upload"}
          size="lg"
          className={parse.isPending ? styles.spin : styles.icon}
        />
        <Swap swapKey={stage} className={styles.title}>
          {parse.isPending ? t("resume.reading") : t("resume.drop")}
        </Swap>
        <span className={styles.limit}>{t("resume.limit")}</span>
      </label>
      {parse.isError ? (
        <Banner tone="critical" title={errorText(parse.error)}>
          {t("resume.manual")}
        </Banner>
      ) : null}
      {parsed === null ? null : <Summary parsed={parsed} />}
      <IconLabel icon="lock" tone="secondary" className={styles.privacy}>
        {t("resume.privacy")}
      </IconLabel>
    </EditorSection>
  )
}
