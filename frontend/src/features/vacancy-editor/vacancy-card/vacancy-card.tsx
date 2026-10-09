import { useState } from "react"
import { gradeIcon, specializationIcon } from "@/entities/catalog"
import { useArchiveVacancy } from "@/entities/vacancy"
import type { Vacancy } from "@/shared/api"
import {
  BackendText,
  useCatalogNames,
  useErrorText,
  useFormatters,
  useMoneyRange,
  useTranslation,
} from "@/shared/i18n"
import { Button, ButtonLink, Card, Chip, ConfirmDialog, IconLabel, Menu, toast } from "@/shared/ui"
import styles from "./vacancy-card.module.css"

export interface VacancyCardProps {
  readonly vacancy: Vacancy
  readonly applications: number
  readonly index: number
  readonly onEdit: (vacancy: Vacancy) => void
}

function sentenceCase(text: string): string {
  return text.charAt(0) + text.slice(1).toLocaleLowerCase()
}

export function VacancyCard({ vacancy, applications, index, onEdit }: VacancyCardProps) {
  const { t } = useTranslation(["vacancyEditor", "catalog", "common"])
  const names = useCatalogNames()
  const format = useFormatters()
  const money = useMoneyRange()
  const errorText = useErrorText()
  const archive = useArchiveVacancy()
  const [asking, setAsking] = useState(false)
  const archived = vacancy.archived_at !== null
  const confirmArchive = () =>
    archive.mutate(vacancy.id, {
      onSuccess: () => {
        setAsking(false)
        toast.success(t("toast.archived"))
      },
      onError: (error) => {
        setAsking(false)
        toast.error(errorText(error))
      },
    })
  return (
    <Card
      as="article"
      motionIndex={index}
      className={styles.card}
      data-archived={archived}
      title={vacancy.title}
      description={
        archived
          ? t("card.archivedAt", { date: format.date(vacancy.archived_at ?? vacancy.updated_at) })
          : t("card.publishedAt", { date: format.date(vacancy.published_at) })
      }
      actions={
        archived ? undefined : (
          <Menu
            label={t("common:action.more")}
            icon="more"
            placement="bottom-end"
            iconOnly
            items={[
              { id: "edit", label: t("card.edit"), icon: "edit", onSelect: () => onEdit(vacancy) },
              {
                id: "archive",
                label: t("card.archive"),
                icon: "revoked",
                onSelect: () => setAsking(true),
              },
            ]}
          />
        )
      }
    >
      <div className={styles.tags}>
        <Chip icon={specializationIcon(vacancy.specialization.code)} tone="accent">
          {names.specialization(vacancy.specialization)}
        </Chip>
        <Chip icon={gradeIcon(vacancy.grade.code)} tone="accent">
          {names.grade(vacancy.grade)}
        </Chip>
      </div>
      {vacancy.description.trim() === "" ? null : (
        <BackendText as="p" className={styles.description}>
          {vacancy.description}
        </BackendText>
      )}
      <ul className={styles.attributes}>
        <li>
          <IconLabel icon="money">{money(vacancy.salary_from, vacancy.salary_to)}</IconLabel>
          <span className={styles.basis}>{t("common:money.basis")}</span>
        </li>
        <li>
          <IconLabel icon="city">
            {sentenceCase(
              format.list(vacancy.work_formats.map((item) => t(`catalog:workFormat.${item}`))),
            )}
          </IconLabel>
        </li>
      </ul>
      <footer className={styles.footer}>
        {applications === 0 ? (
          <IconLabel icon="application" tone="secondary" className={styles.none}>
            {t("card.noApplications")}
          </IconLabel>
        ) : (
          <ButtonLink
            to={`/employer/invitations?tab=applications&vacancy=${vacancy.id}`}
            variant="secondary"
            size="compact"
            icon="application"
          >
            {t("card.applications", { count: applications })}
          </ButtonLink>
        )}
        {archived ? null : (
          <Button variant="ghost" size="compact" icon="edit" onClick={() => onEdit(vacancy)}>
            {t("card.edit")}
          </Button>
        )}
      </footer>
      <ConfirmDialog
        open={asking}
        title={t("archive.title")}
        description={t("archive.text")}
        confirmLabel={t("archive.action")}
        tone="danger"
        pending={archive.isPending}
        onConfirm={confirmArchive}
        onClose={() => setAsking(false)}
      />
    </Card>
  )
}
