import type { ReactNode } from "react"
import { Link } from "react-router"
import { useApplications } from "@/entities/application"
import { candidateTag, InvitationStatusBadge, useSentInvitations } from "@/entities/invitation"
import { useFormatters, useTranslation } from "@/shared/i18n"
import { staggerStyle } from "@/shared/motion"
import { ButtonLink, Card, Icon, IconLabel, type IconName, Skeleton } from "@/shared/ui"
import { candidateCount, latestByNeed, useRecentSelections } from "../recent-selections"
import styles from "./activity-panel.module.css"

const SHOWN = 5

interface Activity {
  readonly id: string
  readonly icon: IconName
  readonly title: string
  readonly at: string
  readonly detail: ReactNode
  readonly to: string
}

function useActivity(): readonly Activity[] | undefined {
  const { t } = useTranslation("employer")
  const sent = useSentInvitations()
  const applications = useApplications()
  const selections = useRecentSelections()
  if (sent.data === undefined || applications.data === undefined) return undefined
  const invitations = sent.data.invitations.map(
    (item): Activity => ({
      id: item.id,
      icon: "invitation",
      title: t("overview.activity.invitation", { tag: candidateTag(item.candidate_id) }),
      at: item.sent_at,
      detail: <InvitationStatusBadge status={item.status} revoked={item.revoked_at !== null} />,
      to: `/employer/invitations/${item.id}`,
    }),
  )
  const responses = applications.data.map(
    (item): Activity => ({
      id: item.id,
      icon: "application",
      title: t("overview.activity.application", { vacancy: item.vacancy_title }),
      at: item.applied_at,
      detail: (
        <InvitationStatusBadge
          status={item.status}
          kind="application"
          revoked={item.revoked_at !== null}
        />
      ),
      to: `/employer/invitations?tab=applications&application=${item.id}`,
    }),
  )
  const built = [...latestByNeed(selections.data ?? []).values()].map(
    (item): Activity => ({
      id: item.id,
      icon: "match",
      title: t("overview.activity.selection", { title: item.title }),
      at: item.created_at,
      detail: (
        <span className={styles.date}>
          {t("overview.activity.found", { count: candidateCount(item) })}
        </span>
      ),
      to: `/employer/selections/${item.id}`,
    }),
  )
  return [...invitations, ...responses, ...built]
    .sort((left, right) => right.at.localeCompare(left.at))
    .slice(0, SHOWN)
}

export interface ActivityPanelProps {
  readonly className?: string | undefined
}

export function ActivityPanel({ className }: ActivityPanelProps) {
  const { t } = useTranslation("employer")
  const format = useFormatters()
  const activity = useActivity()
  return (
    <Card
      title={t("overview.activity.title")}
      className={className}
      motionIndex={3}
      actions={
        <ButtonLink to="/employer/invitations" variant="ghost" size="compact" icon="invitation">
          {t("overview.activity.all")}
        </ButtonLink>
      }
    >
      {activity === undefined ? (
        <Skeleton lines={4} />
      ) : activity.length === 0 ? (
        <IconLabel icon="clock" tone="secondary" className={styles.quiet}>
          {t("overview.activity.empty")}
        </IconLabel>
      ) : (
        <ul className={styles.list}>
          {activity.map((item, index) => (
            <li key={item.id} className={styles.item} style={staggerStyle(index)}>
              <Link to={item.to} className={styles.row} viewTransition>
                <Icon name={item.icon} className={styles.icon} />
                <span className={styles.text}>
                  <span className={styles.title}>{item.title}</span>
                  <span className={styles.meta}>
                    {item.detail}
                    <span className={styles.date}>{format.dateTime(item.at)}</span>
                  </span>
                </span>
                <Icon name="chevron-right" size="sm" className={styles.chevron} />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
