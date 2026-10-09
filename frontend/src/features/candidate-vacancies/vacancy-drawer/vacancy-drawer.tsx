import { gradeIcon, specializationIcon } from "@/entities/catalog"
import type { Application, Vacancy } from "@/shared/api"
import {
  BackendText,
  useCatalogNames,
  useFormatters,
  useMoneyRange,
  useTranslation,
} from "@/shared/i18n"
import { useLatched } from "@/shared/motion"
import { Chip, Dialog, IconLabel, type TermItem, Terms } from "@/shared/ui"
import { ApplyAction } from "../apply-action/apply-action"
import { useWorkFormats } from "../work-formats"
import styles from "./vacancy-drawer.module.css"

export interface VacancyDrawerProps {
  readonly vacancy: Vacancy | undefined
  readonly application: Application | undefined
  readonly onClose: () => void
}

function useTerms(vacancy: Vacancy): readonly TermItem[] {
  const { t } = useTranslation(["vacancies", "catalog", "common"])
  const format = useFormatters()
  const workFormats = useWorkFormats()
  const money = useMoneyRange()
  return [
    {
      key: "salary",
      label: t("terms.salary"),
      icon: "money",
      value: (
        <>
          {money(vacancy.salary_from, vacancy.salary_to)}
          <span className={styles.basis}>{t("common:money.basis")}</span>
        </>
      ),
    },
    {
      key: "formats",
      label: t("terms.formats"),
      icon: "city",
      value: workFormats(vacancy.work_formats),
    },
    {
      key: "published",
      label: t("terms.published"),
      icon: "calendar",
      value: format.date(vacancy.published_at),
    },
  ]
}

function DrawerBody({ vacancy }: { readonly vacancy: Vacancy }) {
  const { t } = useTranslation("vacancies")
  const names = useCatalogNames()
  const terms = useTerms(vacancy)
  return (
    <div className={styles.body}>
      <div className={styles.tags}>
        <Chip icon={specializationIcon(vacancy.specialization.code)} tone="accent">
          {names.specialization(vacancy.specialization)}
        </Chip>
        <Chip icon={gradeIcon(vacancy.grade.code)}>{names.grade(vacancy.grade)}</Chip>
      </div>
      <Terms items={terms} />
      <BackendText as="p" className={styles.description}>
        {vacancy.description}
      </BackendText>
      <IconLabel icon="lock" tone="secondary" className={styles.note}>
        {t("drawer.privacy")}
      </IconLabel>
    </div>
  )
}

export function VacancyDrawer({ vacancy, application, onClose }: VacancyDrawerProps) {
  const open = vacancy !== undefined
  const shown = useLatched(vacancy, open)
  const shownApplication = useLatched(application, open)
  return (
    <Dialog
      open={open}
      onClose={onClose}
      size="drawer"
      title={shown?.title ?? ""}
      description={shown?.company_name}
      actions={
        shown === undefined ? undefined : (
          <ApplyAction vacancy={shown} application={shownApplication} />
        )
      }
    >
      {shown === undefined ? null : <DrawerBody vacancy={shown} />}
    </Dialog>
  )
}
