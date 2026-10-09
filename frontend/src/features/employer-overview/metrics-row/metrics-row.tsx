import { useApplications } from "@/entities/application"
import { useUnreadMessages } from "@/entities/conversation"
import { InvitationBudget, useSentInvitations } from "@/entities/invitation"
import { useTranslation } from "@/shared/i18n"
import { ButtonLink, Card, Skeleton, Stat } from "@/shared/ui"
import styles from "./metrics-row.module.css"

export function MetricsRow() {
  const { t } = useTranslation("employer")
  const sent = useSentInvitations()
  const applications = useApplications()
  const unread = useUnreadMessages("employer")
  const fresh = applications.data?.filter((item) => item.status === "sent").length
  return (
    <Card as="div" aria-label={t("overview.metrics.label")} motionIndex={0}>
      <div className={styles.row}>
        <div className={styles.cell}>
          {sent.data === undefined ? (
            <Skeleton lines={2} />
          ) : (
            <InvitationBudget budget={sent.data.budget} />
          )}
          <ButtonLink
            to="/employer/invitations"
            variant="ghost"
            size="compact"
            icon="arrow-right"
            iconPosition="end"
            className={styles.link}
          >
            {t("overview.metrics.toInvitations")}
          </ButtonLink>
        </div>
        <div className={styles.cell}>
          <Stat
            label={t("overview.metrics.applications")}
            value={fresh === undefined ? null : String(fresh)}
            icon="application"
            size="large"
            tone={fresh !== undefined && fresh > 0 ? "attention" : "default"}
          />
          <ButtonLink
            to="/employer/invitations?tab=applications"
            variant="ghost"
            size="compact"
            icon="arrow-right"
            iconPosition="end"
            className={styles.link}
          >
            {t("overview.metrics.toApplications")}
          </ButtonLink>
        </div>
        <div className={styles.cell}>
          <Stat
            label={t("overview.metrics.messages")}
            value={String(unread)}
            icon="message"
            size="large"
          />
          <ButtonLink
            to="/employer/invitations"
            variant="ghost"
            size="compact"
            icon="arrow-right"
            iconPosition="end"
            className={styles.link}
          >
            {t("overview.metrics.toMessages")}
          </ButtonLink>
        </div>
      </div>
    </Card>
  )
}
