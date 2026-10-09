import { InvitationBudget, useSentInvitations } from "@/entities/invitation"
import { ConversationThread } from "@/features/conversation"
import { InvitationDetail, InvitationList } from "@/features/employer-invitations"
import { useTranslation } from "@/shared/i18n"
import { Card, EmptyState, IconLabel, LoadError, Skeleton } from "@/shared/ui"
import { Inbox } from "../inbox/inbox"
import styles from "./invitations-tab.module.css"

export interface InvitationsTabProps {
  readonly selectedId: string | null
}

export function InvitationsTab({ selectedId }: InvitationsTabProps) {
  const { t } = useTranslation("employer")
  const sent = useSentInvitations()
  if (sent.isError)
    return (
      <LoadError error={sent.error} onRetry={() => void sent.refetch()} pending={sent.isFetching} />
    )
  if (sent.data === undefined) return <Skeleton shape="block" />
  const selected = sent.data.invitations.find((item) => item.id === selectedId)
  const detail =
    selected !== undefined ? (
      <InvitationDetail
        invitation={selected}
        conversation={<ConversationThread invitationId={selected.id} side="employer" />}
      />
    ) : (
      <Card as="div">
        <EmptyState
          icon={selectedId === null ? "invitation" : "alert"}
          title={t(selectedId === null ? "invitations.pickTitle" : "invitations.missingTitle")}
          description={t(selectedId === null ? "invitations.pickText" : "invitations.missingText")}
        />
      </Card>
    )
  return (
    <div className={styles.tab}>
      <div className={styles.budget}>
        <InvitationBudget budget={sent.data.budget} className={styles.meter} />
        <IconLabel icon="info" tone="secondary" size="sm">
          {t("invitations.budgetHint")}
        </IconLabel>
      </div>
      <Inbox
        label={t("invitations.listLabel")}
        list={<InvitationList invitations={sent.data.invitations} selectedId={selectedId} />}
        detail={detail}
        selectedKey={selectedId}
        backTo="/employer/invitations"
      />
    </div>
  )
}
