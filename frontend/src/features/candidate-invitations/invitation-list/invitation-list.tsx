import { InboxStatusBadge } from "@/entities/invitation"
import type { Invitation } from "@/shared/api"
import { BackendText, useFormatters, useMoneyRange, useTranslation } from "@/shared/i18n"
import { EmptyState, Icon, ListRow } from "@/shared/ui"
import styles from "./invitation-list.module.css"

export interface InvitationListProps {
  readonly invitations: readonly Invitation[]
  readonly selectedId: string | null
}

function isQuiet(invitation: Invitation): boolean {
  return (
    invitation.status === "declined" ||
    invitation.status === "expired" ||
    invitation.revoked_at !== null
  )
}

export function InvitationList({ invitations, selectedId }: InvitationListProps) {
  const { t } = useTranslation(["invitations", "common"])
  const format = useFormatters()
  const money = useMoneyRange()
  if (invitations.length === 0)
    return (
      <EmptyState
        icon="invitation"
        title={t("list.emptyTitle")}
        description={t("list.emptyText")}
      />
    )
  return (
    <>
      <ul className={styles.list} aria-label={t("list.label")}>
        {invitations.map((invitation, index) => (
          <ListRow
            key={invitation.id}
            to={`/candidate/invitations/${invitation.id}`}
            selected={invitation.id === selectedId}
            quiet={isQuiet(invitation)}
            motionIndex={index}
            leading={<Icon name="company" />}
            title={
              <span className={styles.title} data-new={invitation.status === "sent"}>
                <BackendText>{invitation.company_name}</BackendText>
              </span>
            }
            meta={
              <>
                <span className={styles.figure}>
                  {money(invitation.salary_from, invitation.salary_to)}
                </span>
                <span className={styles.figure}>{format.date(invitation.sent_at)}</span>
                <InboxStatusBadge
                  status={invitation.status}
                  revoked={invitation.revoked_at !== null}
                />
              </>
            }
            trailing={
              invitation.unread_messages > 0 ? (
                <span className={styles.unread}>
                  <Icon name="message" size="sm" />
                  {invitation.unread_messages}
                  <span className="visually-hidden">
                    {t("list.unread", { count: invitation.unread_messages })}
                  </span>
                </span>
              ) : undefined
            }
          />
        ))}
      </ul>
      <p className={styles.basis}>{t("common:money.basis")}</p>
    </>
  )
}
