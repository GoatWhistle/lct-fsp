import { useTranslation } from "@/shared/i18n"
import { Card, PhoneField, TextField } from "@/shared/ui"
import type { CompanyCardProps } from "../about-card/about-card"
import styles from "./contacts-card.module.css"

export function ContactsCard({ form, error, onChange, className }: CompanyCardProps) {
  const { t } = useTranslation("company")
  return (
    <Card level="section" title={t("sections.contacts")} motionIndex={1} className={className}>
      <div className={styles.fields}>
        <TextField
          label={t("fields.website")}
          type="text"
          inputMode="url"
          icon="link"
          autoComplete="url"
          value={form.website}
          onChange={(website) => onChange({ website })}
          maxLength={300}
          placeholder={t("fields.websitePlaceholder")}
          error={error("website")}
        />
        <TextField
          label={t("fields.email")}
          type="text"
          inputMode="email"
          icon="mail"
          autoComplete="email"
          value={form.email}
          onChange={(email) => onChange({ email })}
          placeholder={t("fields.emailPlaceholder")}
          error={error("email")}
          required
        />
        <PhoneField
          label={t("fields.phone")}
          value={form.phone}
          onChange={(phone) => onChange({ phone })}
          placeholder={t("fields.phonePlaceholder")}
          error={error("phone")}
        />
      </div>
    </Card>
  )
}
