import { useParams } from "react-router"
import { CandidateInbox } from "@/features/candidate-invitations"
import { CategoryGate } from "@/features/candidate-overview"
import { ConversationThread } from "@/features/conversation"
import { useDocumentTitle, useTranslation } from "@/shared/i18n"
import { PageBody, PageHeader } from "@/shared/ui"

export function CandidateInvitationsPage() {
  const { t } = useTranslation("invitations")
  const { id } = useParams()
  useDocumentTitle(t("title"))
  return (
    <>
      <PageHeader title={t("title")} description={t("lead")} />
      <PageBody>
        <CategoryGate topic="invitations">
          <CandidateInbox
            selectedId={id ?? null}
            conversation={(invitationId) => (
              <ConversationThread invitationId={invitationId} side="candidate" />
            )}
          />
        </CategoryGate>
      </PageBody>
    </>
  )
}
