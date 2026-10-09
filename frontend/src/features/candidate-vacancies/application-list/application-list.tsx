import { useState } from "react"
import { Link } from "react-router"
import { InboxStatusBadge, isOpenStatus } from "@/entities/invitation"
import { useMyApplications, useRevokeApplication } from "@/entities/vacancy"
import type { Application } from "@/shared/api"
import {
  BackendText,
  useErrorText,
  useFormatters,
  useMoneyRange,
  useTranslation,
} from "@/shared/i18n"
import { staggerStyle, useLatched } from "@/shared/motion"
import {
  ButtonLink,
  Card,
  ConfirmDialog,
  EmptyState,
  IconLabel,
  LoadError,
  Menu,
  Skeleton,
  toast,
} from "@/shared/ui"
import styles from "./application-list.module.css"

interface RowProps {
  readonly application: Application
  readonly index: number
  readonly onRevoke: (application: Application) => void
}

function ApplicationRow({ application, index, onRevoke }: RowProps) {
  const { t } = useTranslation(["vacancies", "common"])
  const format = useFormatters()
  const money = useMoneyRange()
  const revoked = application.revoked_at !== null
  const revocable =
    !revoked && application.status !== "declined" && application.status !== "expired"
  return (
    <li className={styles.row} style={staggerStyle(index)} data-quiet={revoked}>
      <div className={styles.main}>
        <Link to={`/candidate/vacancies/${application.vacancy_id}`} className={styles.title}>
          <BackendText>{application.vacancy_title}</BackendText>
        </Link>
        <span className={styles.meta}>
          <IconLabel icon="company" tone="secondary" size="sm">
            <BackendText>{application.company_name}</BackendText>
          </IconLabel>
          <IconLabel icon="money" tone="secondary" size="sm">
            {money(application.salary_from, application.salary_to)}
          </IconLabel>
          <IconLabel icon="send" tone="secondary" size="sm">
            {t("applications.applied", { date: format.date(application.applied_at) })}
          </IconLabel>
          {isOpenStatus(application.status) && !revoked ? (
            <IconLabel icon="deadline" tone="secondary" size="sm">
              {t("applications.expires", { date: format.dateMoscow(application.expires_at) })}
            </IconLabel>
          ) : null}
        </span>
      </div>
      <div className={styles.side}>
        <InboxStatusBadge kind="application" status={application.status} revoked={revoked} />
        {revocable ? (
          <Menu
            label={t("common:action.more")}
            icon="more"
            iconOnly
            placement="bottom-end"
            items={[
              {
                id: "revoke",
                label: t("applications.revoke"),
                icon: "revoked",
                onSelect: () => onRevoke(application),
              },
            ]}
          />
        ) : null}
      </div>
    </li>
  )
}

export function ApplicationList() {
  const { t } = useTranslation(["vacancies", "common"])
  const errorText = useErrorText()
  const applications = useMyApplications()
  const revoke = useRevokeApplication()
  const [asked, setAsked] = useState<Application | null>(null)
  const shown = useLatched(asked, asked !== null)
  if (applications.isError)
    return (
      <LoadError
        error={applications.error}
        onRetry={() => void applications.refetch()}
        pending={applications.isFetching}
      />
    )
  if (applications.data === undefined) return <Skeleton shape="block" />
  if (applications.data.length === 0)
    return (
      <EmptyState
        size="hero"
        icon="application"
        title={t("applications.emptyTitle")}
        description={t("applications.emptyText")}
        action={
          <ButtonLink to="/candidate/vacancies" icon="vacancy">
            {t("applications.toVacancies")}
          </ButtonLink>
        }
      />
    )
  const confirm = (application: Application) =>
    revoke.mutate(application.id, {
      onSuccess: () => {
        setAsked(null)
        toast.success(t("toast.revoked"))
      },
      onError: (error) => {
        setAsked(null)
        toast.error(errorText(error))
      },
    })
  return (
    <Card title={t("applications.title")} description={t("applications.lead")}>
      <ul className={styles.list}>
        {applications.data.map((application, index) => (
          <ApplicationRow
            key={application.id}
            application={application}
            index={index}
            onRevoke={setAsked}
          />
        ))}
      </ul>
      <p className={styles.basis}>{t("common:money.basis")}</p>
      <ConfirmDialog
        open={asked !== null}
        tone="danger"
        title={t("applications.revokeTitle")}
        description={t("applications.revokeText", { company: shown?.company_name ?? "" })}
        confirmLabel={t("applications.revoke")}
        pending={revoke.isPending}
        onConfirm={() => {
          if (asked !== null) confirm(asked)
        }}
        onClose={() => setAsked(null)}
      />
    </Card>
  )
}
