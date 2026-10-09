import { useTechnologies } from "@/entities/catalog"
import { useTranslation } from "@/shared/i18n"
import { Combobox, Skeleton } from "@/shared/ui"
import { EditorSection } from "../editor-section/editor-section"
import type { DraftSectionProps } from "../profile-draft"
import { useFieldHint } from "../use-field-hint"

export function StackSection({ draft, onChange, marks }: DraftSectionProps) {
  const { t } = useTranslation("profile")
  const hint = useFieldHint(marks)
  const technologies = useTechnologies()
  return (
    <EditorSection id="stack" title={t("sections.stack")} description={t("fields.stackLead")}>
      {technologies.data === undefined ? (
        <Skeleton lines={2} />
      ) : (
        <Combobox
          label={t("fields.stack")}
          values={draft.stack}
          onChange={(stack) => onChange({ stack })}
          options={technologies.data.map((item) => ({ value: item.code, label: item.name }))}
          hint={hint("stack", t("fields.stackHint"))}
        />
      )}
    </EditorSection>
  )
}
