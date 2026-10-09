import { Link } from "react-router"
import { gradeIcon, specializationIcon } from "@/entities/catalog"
import { InboxStatusBadge } from "@/entities/invitation"
import type { Application, Vacancy } from "@/shared/api"
import {
  BackendText,
  useCatalogNames,
  useFormatters,
  useMoneyRange,
  useTranslation,
} from "@/shared/i18n"
import { Card, Chip, Icon, IconLabel } from "@/shared/ui"
import { useWorkFormats } from "../work-formats"
import styles from "./vacancy-card.module.css"

export interface VacancyCardProps {
  readonly vacancy: Vacancy
  readonly application: Application | undefined
  readonly to: string
  readonly index: number
}

export function VacancyCard({ vacancy, application, to, index }: VacancyCardProps) {
  const { t } = useTranslation(["vacancies", "catalog"])
  const names = useCatalogNames()
  const format = useFormatters()
  const workFormats = useWorkFormats()
  const money = useMoneyRange()
  return (
    <Card
      as="article"
      motionIndex={index}
      className={styles.card}
      title={
        <Link to={to} className={styles.link}>
          <BackendText>{vacancy.title}</BackendText>
        </Link>
      }
      description={<BackendText>{vacancy.company_name}</BackendText>}
    >
      <div className={styles.tags}>
        <Chip icon={specializationIcon(vacancy.specialization.code)} tone="accent">
          {names.specialization(vacancy.specialization)}
        </Chip>
        <Chip icon={gradeIcon(vacancy.grade.code)}>{names.grade(vacancy.grade)}</Chip>
      </div>
      <ul className={styles.attributes}>
        <li>
          <IconLabel icon="money">{money(vacancy.salary_from, vacancy.salary_to)}</IconLabel>
        </li>
        <li>
          <IconLabel icon="city" tone="secondary">
            {workFormats(vacancy.work_formats)}
          </IconLabel>
        </li>
      </ul>
      <footer className={styles.footer}>
        {application === undefined ? (
          <IconLabel icon="calendar" tone="secondary" size="sm">
            {t("card.published", { date: format.date(vacancy.published_at) })}
          </IconLabel>
        ) : (
          <InboxStatusBadge
            kind="application"
            status={application.status}
            revoked={application.revoked_at !== null}
          />
        )}
        <Icon name="arrow-right" className={styles.arrow} />
      </footer>
    </Card>
  )
}
