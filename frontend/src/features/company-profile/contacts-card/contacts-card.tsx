import { useTranslation } from "@/shared/i18n"
import { Card, TextField } from "@/shared/ui"
import type { CompanyCardProps } from "../about-card/about-card"
import styles from "./contacts-card.module.css"

export function ContactsCard({ form, error, onChange, className }: CompanyCardProps) {
  const { t } = useTranslation("company")
  return (
    <Card
      title={t("sections.contacts")}
      description={t("sections.contactsLead")}
      motionIndex={1}
      className={className}
    >
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
          hint={t("fields.websiteHint")}
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
        />
        <TextField
          label={t("fields.phone")}
          type="tel"
          icon="phone"
          autoComplete="tel"
          value={form.phone}
          onChange={(phone) => onChange({ phone })}
          maxLength={32}
          placeholder={t("fields.phonePlaceholder")}
          hint={t("fields.phoneHint")}
        />
      </div>
    </Card>
  )
}
