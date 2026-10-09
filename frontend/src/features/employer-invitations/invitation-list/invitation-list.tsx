import { candidateTag, InvitationStatusBadge } from "@/entities/invitation"
import type { Invitation } from "@/shared/api"
import { useFormatters, useMoneyRange, useTranslation } from "@/shared/i18n"
import { ButtonLink, EmptyState, Icon, ListRow } from "@/shared/ui"
import styles from "./invitation-list.module.css"

export interface InvitationListProps {
  readonly invitations: readonly Invitation[]
  readonly selectedId: string | null
}

export function InvitationList({ invitations, selectedId }: InvitationListProps) {
  const { t } = useTranslation("employer")
  const format = useFormatters()
  const money = useMoneyRange()
  if (invitations.length === 0)
    return (
      <EmptyState
        icon="invitation"
        title={t("invitations.emptyTitle")}
        description={t("invitations.emptyText")}
        action={
          <ButtonLink to="/employer/needs" icon="need" variant="secondary">
            {t("invitations.toNeeds")}
          </ButtonLink>
        }
      />
    )
  return (
    <ul className={styles.list} aria-label={t("invitations.listLabel")}>
      {invitations.map((invitation, index) => (
        <ListRow
          key={invitation.id}
          to={`/employer/invitations/${invitation.id}`}
          selected={invitation.id === selectedId}
          quiet={invitation.status === "declined" || invitation.status === "expired"}
          motionIndex={index}
          leading={<Icon name="invitation" />}
          title={
            <span className={styles.tag}>
              {t("invitations.candidate", { tag: candidateTag(invitation.candidate_id) })}
            </span>
          }
          meta={
            <>
              <span className={styles.money}>
                {money(invitation.salary_from, invitation.salary_to)}
              </span>
              <span>{format.date(invitation.sent_at)}</span>
            </>
          }
          trailing={
            <>
              <InvitationStatusBadge
                status={invitation.status}
                revoked={invitation.revoked_at !== null}
              />
              {invitation.unread_messages > 0 ? (
                <span className={styles.unread}>
                  <Icon name="message" size="sm" />
                  {t("invitations.unread", { count: invitation.unread_messages })}
                </span>
              ) : null}
            </>
          }
        />
      ))}
    </ul>
  )
}
