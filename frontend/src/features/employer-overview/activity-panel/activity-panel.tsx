import { Link } from "react-router"
import { useApplications } from "@/entities/application"
import {
  candidateTag,
  InvitationStatusBadge,
  type ResponseKind,
  useSentInvitations,
} from "@/entities/invitation"
import type { InvitationStatus } from "@/shared/api"
import { useFormatters, useTranslation } from "@/shared/i18n"
import { staggerStyle } from "@/shared/motion"
import { ButtonLink, Card, EmptyState, Icon, Skeleton } from "@/shared/ui"
import styles from "./activity-panel.module.css"

const SHOWN = 6

interface Activity {
  readonly id: string
  readonly kind: ResponseKind
  readonly title: string
  readonly at: string
  readonly status: InvitationStatus
  readonly revoked: boolean
  readonly to: string
}

function useActivity(): readonly Activity[] | undefined {
  const { t } = useTranslation("employer")
  const sent = useSentInvitations()
  const applications = useApplications()
  if (sent.data === undefined || applications.data === undefined) return undefined
  const invitations = sent.data.invitations.map(
    (item): Activity => ({
      id: item.id,
      kind: "invitation",
      title: t("overview.activity.invitation", { tag: candidateTag(item.candidate_id) }),
      at: item.sent_at,
      status: item.status,
      revoked: item.revoked_at !== null,
      to: `/employer/invitations/${item.id}`,
    }),
  )
  const responses = applications.data.map(
    (item): Activity => ({
      id: item.id,
      kind: "application",
      title: t("overview.activity.application", { vacancy: item.vacancy_title }),
      at: item.applied_at,
      status: item.status,
      revoked: item.revoked_at !== null,
      to: `/employer/invitations?tab=applications&application=${item.id}`,
    }),
  )
  return [...invitations, ...responses]
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
      motionIndex={2}
      actions={
        <ButtonLink to="/employer/invitations" variant="ghost" size="compact" icon="invitation">
          {t("overview.activity.all")}
        </ButtonLink>
      }
    >
      {activity === undefined ? (
        <Skeleton lines={5} />
      ) : activity.length === 0 ? (
        <EmptyState
          icon="invitation"
          title={t("overview.activity.emptyTitle")}
          description={t("overview.activity.emptyText")}
        />
      ) : (
        <ul className={styles.list}>
          {activity.map((item, index) => (
            <li key={item.id} className={styles.item} style={staggerStyle(index)}>
              <Link to={item.to} className={styles.row} viewTransition>
                <Icon name={item.kind} className={styles.icon} />
                <span className={styles.text}>
                  <span className={styles.title}>{item.title}</span>
                  <span className={styles.meta}>
                    <InvitationStatusBadge
                      status={item.status}
                      kind={item.kind}
                      revoked={item.revoked}
                    />
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
