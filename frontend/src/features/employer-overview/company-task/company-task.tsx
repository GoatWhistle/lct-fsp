import { useTranslation } from "@/shared/i18n"
import { ButtonLink, Card, IconLabel } from "@/shared/ui"
import styles from "./company-task.module.css"

export function CompanyTask() {
  const { t } = useTranslation("employer")
  return (
    <Card tone="inverse" title={t("overview.company.title")} motionIndex={0}>
      <div className={styles.body}>
        <p className={styles.text}>{t("overview.company.text")}</p>
        <ul className={styles.points}>
          <li>
            <IconLabel icon="invitation">{t("overview.company.invitations")}</IconLabel>
          </li>
          <li>
            <IconLabel icon="vacancy">{t("overview.company.vacancies")}</IconLabel>
          </li>
          <li>
            <IconLabel icon="task">{t("overview.company.tasks")}</IconLabel>
          </li>
        </ul>
        <div>
          <ButtonLink to="/employer/company" icon="company">
            {t("overview.company.action")}
          </ButtonLink>
        </div>
      </div>
    </Card>
  )
}
