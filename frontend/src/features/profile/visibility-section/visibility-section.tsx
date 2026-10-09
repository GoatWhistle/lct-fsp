import type { HideableField } from "@/shared/api"
import { useTranslation } from "@/shared/i18n"
import { IconLabel, Switch } from "@/shared/ui"
import { EditorSection } from "../editor-section/editor-section"
import { type DraftSectionProps, HIDEABLE } from "../profile-draft"
import styles from "./visibility-section.module.css"

export function VisibilitySection({ draft, onChange }: DraftSectionProps) {
  const { t } = useTranslation("profile")
  const toggle = (field: HideableField, visible: boolean) =>
    onChange({
      hidden: visible
        ? draft.hidden.filter((item) => item !== field)
        : HIDEABLE.filter((item) => item === field || draft.hidden.includes(item)),
    })
  return (
    <EditorSection
      id="visibility"
      title={t("sections.visibility")}
      description={t("visibility.lead")}
    >
      <ul className={styles.list}>
        {HIDEABLE.map((field) => {
          const visible = !draft.hidden.includes(field)
          return (
            <li key={field} className={styles.row}>
              <Switch
                label={t(`hideable.${field}`)}
                checked={visible}
                onChange={(on) => toggle(field, on)}
              />
              <IconLabel
                icon={visible ? "eye" : "lock"}
                tone={visible ? "accent" : "secondary"}
                className={styles.state}
              >
                {visible ? t("visibility.shown") : t("visibility.hidden")}
              </IconLabel>
            </li>
          )
        })}
      </ul>
      <div className={styles.rules}>
        <IconLabel icon="eye" tone="secondary">
          {t("visibility.always")}
        </IconLabel>
        <IconLabel icon="lock" tone="secondary">
          {t("visibility.never")}
        </IconLabel>
      </div>
    </EditorSection>
  )
}
