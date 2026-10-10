import { useTechnologies } from "@/entities/catalog"
import { useTranslation } from "@/shared/i18n"
import { Combobox, Skeleton } from "@/shared/ui"
import { EditorSection } from "../editor-section/editor-section"
import type { DraftSectionProps } from "../profile-draft"
import { useFieldHint } from "../use-field-hint"
import styles from "./stack-section.module.css"

export function StackSection({ draft, onChange, marks }: DraftSectionProps) {
  const { t } = useTranslation("profile")
  const hint = useFieldHint(marks)
  const technologies = useTechnologies()
  return (
    <EditorSection id="stack" title={t("sections.stack")}>
      {technologies.data === undefined ? (
        <Skeleton lines={2} />
      ) : (
        <Combobox
          label={t("fields.stack")}
          hideLabel
          values={draft.stack}
          onChange={(stack) => onChange({ stack })}
          options={technologies.data.map((item) => ({ value: item.code, label: item.name }))}
          hint={hint("stack")}
          className={styles.wide}
        />
      )}
    </EditorSection>
  )
}
