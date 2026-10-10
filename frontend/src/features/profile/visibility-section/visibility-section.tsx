import type { HideableField } from "@/shared/api"
import { useTranslation } from "@/shared/i18n"
import { FlagList, FlagRow, Icon, type IconName, Switch } from "@/shared/ui"
import { EditorSection } from "../editor-section/editor-section"
import { type DraftSectionProps, HIDEABLE } from "../profile-draft"

const MARKS: Readonly<Record<HideableField, IconName>> = {
  stack: "topic",
  experience_years: "clock",
  city: "city",
  relocation: "benefit-relocation",
  industries: "company",
}

export function VisibilitySection({ draft, onChange }: DraftSectionProps) {
  const { t } = useTranslation("profile")
  const toggle = (field: HideableField, visible: boolean) =>
    onChange({
      hidden: visible
        ? draft.hidden.filter((item) => item !== field)
        : HIDEABLE.filter((item) => item === field || draft.hidden.includes(item)),
    })
  return (
    <EditorSection id="visibility" title={t("sections.visibility")}>
      <FlagList>
        {HIDEABLE.map((field) => {
          const visible = !draft.hidden.includes(field)
          return (
            <FlagRow
              key={field}
              mark={<Icon name={visible ? MARKS[field] : "lock"} size="md" />}
              title={t(`hideable.${field}`)}
              note={visible ? t("visibility.shown") : t("visibility.hidden")}
              active={visible}
              trailing={
                <Switch
                  label={t(`hideable.${field}`)}
                  hideLabel
                  checked={visible}
                  onChange={(on) => toggle(field, on)}
                />
              }
            />
          )
        })}
      </FlagList>
    </EditorSection>
  )
}
