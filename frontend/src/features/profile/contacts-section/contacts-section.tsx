import { useTranslation } from "@/shared/i18n"
import { PhoneField, TextField } from "@/shared/ui"
import { EditorSection } from "../editor-section/editor-section"
import type { DraftSectionProps } from "../profile-draft"
import { useFieldHint } from "../use-field-hint"
import styles from "./contacts-section.module.css"

export function ContactsSection({ draft, onChange, errors, marks }: DraftSectionProps) {
  const { t } = useTranslation("profile")
  const hint = useFieldHint(marks)
  return (
    <EditorSection id="contacts" title={t("sections.contacts")}>
      <div className={styles.grid}>
        <TextField
          label={t("fields.email")}
          type="email"
          icon="mail"
          autoComplete="email"
          value={draft.contact_email}
          onChange={(contact_email) => onChange({ contact_email })}
          hint={hint("contact_email")}
          error={errors.contact_email}
          required
        />
        <PhoneField
          label={t("fields.phone")}
          value={draft.contact_phone}
          onChange={(contact_phone) => onChange({ contact_phone })}
          hint={hint("contact_phone")}
          error={errors.contact_phone}
          placeholder={t("fields.phonePlaceholder")}
        />
        <TextField
          label={t("fields.telegram")}
          icon="telegram"
          value={draft.telegram}
          onChange={(telegram) => onChange({ telegram })}
          placeholder={t("fields.telegramPlaceholder")}
          hint={hint("telegram")}
        />
      </div>
    </EditorSection>
  )
}
