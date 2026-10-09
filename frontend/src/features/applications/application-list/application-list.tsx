import { candidateTag, InvitationStatusBadge } from "@/entities/invitation"
import type { Application } from "@/shared/api"
import { useFormatters, useTranslation } from "@/shared/i18n"
import { ButtonLink, EmptyState, Icon, ListRow } from "@/shared/ui"
import styles from "./application-list.module.css"

export interface ApplicationListProps {
  readonly applications: readonly Application[]
  readonly selectedId: string | null
  readonly linkTo: (id: string) => string
}

export function ApplicationList({ applications, selectedId, linkTo }: ApplicationListProps) {
  const { t } = useTranslation("applications")
  const format = useFormatters()
  if (applications.length === 0)
    return (
      <EmptyState
        icon="application"
        title={t("emptyTitle")}
        description={t("emptyText")}
        action={
          <ButtonLink to="/employer/vacancies" icon="vacancy" variant="secondary">
            {t("toVacancies")}
          </ButtonLink>
        }
      />
    )
  return (
    <ul className={styles.list} aria-label={t("listLabel")}>
      {applications.map((application, index) => (
        <ListRow
          key={application.id}
          to={linkTo(application.id)}
          selected={application.id === selectedId}
          quiet={application.status === "declined" || application.status === "expired"}
          motionIndex={index}
          leading={<Icon name="application" />}
          title={application.vacancy_title}
          meta={
            <>
              <span className={styles.tag}>
                {t("candidate", { tag: candidateTag(application.candidate_id) })}
              </span>
              <span>{format.date(application.applied_at)}</span>
            </>
          }
          trailing={
            <InvitationStatusBadge
              status={application.status}
              kind="application"
              revoked={application.revoked_at !== null}
            />
          }
        />
      ))}
    </ul>
  )
}
