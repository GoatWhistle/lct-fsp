import type { Disclosed } from "@/shared/api"
import { useTranslation } from "@/shared/i18n"
import { Card, Chip, IconLabel } from "@/shared/ui"
import styles from "./contacts-record.module.css"

export interface ContactsRecordProps {
  readonly disclosed: Disclosed
}

function telegramLink(handle: string): string {
  return `tg://resolve?domain=${handle.replace(/^@/, "")}`
}

export function ContactsRecord({ disclosed }: ContactsRecordProps) {
  const { t } = useTranslation("card")
  return (
    <Card title={t("contacts.title")} description={t("contacts.lead")}>
      <div className={styles.body}>
        <div className={styles.links}>
          <a className={styles.link} href={`mailto:${disclosed.contact_email}`}>
            <IconLabel icon="mail">{disclosed.contact_email}</IconLabel>
          </a>
          {disclosed.contact_phone === null ? null : (
            <a className={styles.link} href={`tel:${disclosed.contact_phone}`}>
              <IconLabel icon="phone">{disclosed.contact_phone}</IconLabel>
            </a>
          )}
          {disclosed.telegram === null ? null : (
            <a className={styles.link} href={telegramLink(disclosed.telegram)}>
              <IconLabel icon="telegram">{disclosed.telegram}</IconLabel>
            </a>
          )}
        </div>
        {disclosed.about.trim() === "" ? null : (
          <div className={styles.group}>
            <span className={styles.label}>{t("contacts.about")}</span>
            <p className={styles.about}>{disclosed.about}</p>
          </div>
        )}
        {disclosed.job_roles.length === 0 ? null : (
          <div className={styles.group}>
            <span className={styles.label}>{t("contacts.roles")}</span>
            <span className={styles.chips}>
              {disclosed.job_roles.map((role) => (
                <Chip key={role}>{role}</Chip>
              ))}
            </span>
          </div>
        )}
        {disclosed.soft_skills.length === 0 ? null : (
          <div className={styles.group}>
            <span className={styles.label}>{t("contacts.soft")}</span>
            <span className={styles.chips}>
              {disclosed.soft_skills.map((skill) => (
                <Chip key={skill}>{skill}</Chip>
              ))}
            </span>
          </div>
        )}
      </div>
    </Card>
  )
}
