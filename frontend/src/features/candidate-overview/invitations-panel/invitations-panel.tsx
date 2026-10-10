import { Link } from "react-router"
import { InboxStatusBadge, useInbox } from "@/entities/invitation"
import { BackendText, useMoneyRange, useTranslation } from "@/shared/i18n"
import { staggerStyle } from "@/shared/motion"
import { ButtonLink, Card, IconLabel, LoadError, Skeleton } from "@/shared/ui"
import styles from "./invitations-panel.module.css"

const LATEST = 3

export interface InvitationsPanelProps {
  readonly motionIndex?: number
  readonly className?: string | undefined
}

function Latest() {
  const { t } = useTranslation("overview")
  const common = useTranslation().t
  const money = useMoneyRange()
  const inbox = useInbox()
  if (inbox.isError)
    return (
      <LoadError
        error={inbox.error}
        onRetry={() => void inbox.refetch()}
        pending={inbox.isFetching}
      />
    )
  if (inbox.data === undefined) return <Skeleton lines={3} />
  if (inbox.data.length === 0)
    return (
      <div className={styles.empty}>
        <IconLabel icon="invitation" tone="secondary">
          {t("invitations.emptyTitle")}
        </IconLabel>
        <p className={styles.basis}>{t("invitations.emptyText")}</p>
      </div>
    )
  return (
    <>
      <ul className={styles.list}>
        {inbox.data.slice(0, LATEST).map((invitation, index) => (
          <li key={invitation.id} className={styles.item} style={staggerStyle(index)}>
            <Link
              to={`/candidate/invitations/${invitation.id}`}
              className={styles.link}
              data-new={invitation.status === "sent"}
              viewTransition
            >
              <BackendText className={styles.company}>{invitation.company_name}</BackendText>
              <IconLabel icon="money" tone="secondary" className={styles.money}>
                {money(invitation.salary_from, invitation.salary_to)}
              </IconLabel>
            </Link>
            <InboxStatusBadge status={invitation.status} revoked={invitation.revoked_at !== null} />
          </li>
        ))}
      </ul>
      <p className={styles.basis}>{common("money.basis")}</p>
    </>
  )
}

export function InvitationsPanel({ motionIndex, className }: InvitationsPanelProps) {
  const { t } = useTranslation("overview")
  return (
    <Card
      title={t("invitations.title")}
      motionIndex={motionIndex}
      className={className}
      actions={
        <ButtonLink
          to="/candidate/invitations"
          variant="ghost"
          size="compact"
          icon="arrow-right"
          iconPosition="end"
        >
          {t("invitations.all")}
        </ButtonLink>
      }
    >
      <Latest />
    </Card>
  )
}
