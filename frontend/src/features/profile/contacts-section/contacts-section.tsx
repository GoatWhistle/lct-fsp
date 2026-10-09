import { useTranslation } from "@/shared/i18n"
import { IconLabel, TextField } from "@/shared/ui"
import { EditorSection, FieldRow } from "../editor-section/editor-section"
import type { DraftSectionProps } from "../profile-draft"
import { useFieldHint } from "../use-field-hint"

export function ContactsSection({ draft, onChange, errors, marks }: DraftSectionProps) {
  const { t } = useTranslation("profile")
  const hint = useFieldHint(marks)
  return (
    <EditorSection id="contacts" title={t("sections.contacts")}>
      <IconLabel icon="lock" tone="secondary">
        {t("fields.contactsNote")}
      </IconLabel>
      <FieldRow>
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
        <TextField
          label={t("fields.phone")}
          type="tel"
          icon="phone"
          autoComplete="tel"
          value={draft.contact_phone}
          onChange={(contact_phone) => onChange({ contact_phone })}
          hint={hint("contact_phone")}
        />
        <TextField
          label={t("fields.telegram")}
          icon="telegram"
          value={draft.telegram}
          onChange={(telegram) => onChange({ telegram })}
          placeholder={t("fields.telegramPlaceholder")}
          hint={hint("telegram")}
        />
      </FieldRow>
    </EditorSection>
  )
}
