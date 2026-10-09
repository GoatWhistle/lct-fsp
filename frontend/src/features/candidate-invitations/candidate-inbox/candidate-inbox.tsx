import { type ReactNode, useEffect, useRef } from "react"
import { useInbox, useInboxAction } from "@/entities/invitation"
import type { Invitation } from "@/shared/api"
import { useTranslation } from "@/shared/i18n"
import { EmptyState, LoadError, Skeleton } from "@/shared/ui"
import { InboxLayout } from "../inbox-layout/inbox-layout"
import { InvitationDetail } from "../invitation-detail/invitation-detail"
import { InvitationList } from "../invitation-list/invitation-list"
import styles from "./candidate-inbox.module.css"

export interface CandidateInboxProps {
  readonly selectedId: string | null
  readonly conversation: (invitationId: string) => ReactNode
}

function useMarkViewed(selected: Invitation | undefined) {
  const view = useInboxAction("view")
  const marked = useRef(new Set<string>())
  const { mutate } = view
  useEffect(() => {
    if (selected === undefined || selected.status !== "sent") return
    if (marked.current.has(selected.id)) return
    marked.current.add(selected.id)
    mutate(selected.id)
  }, [selected, mutate])
}

export function CandidateInbox({ selectedId, conversation }: CandidateInboxProps) {
  const { t } = useTranslation("invitations")
  const inbox = useInbox()
  const selected = inbox.data?.find((item) => item.id === selectedId)
  useMarkViewed(selected)
  if (inbox.isError)
    return (
      <LoadError
        error={inbox.error}
        onRetry={() => void inbox.refetch()}
        pending={inbox.isFetching}
      />
    )
  if (inbox.data === undefined) return <Skeleton shape="block" />
  if (inbox.data.length === 0)
    return (
      <EmptyState
        size="hero"
        icon="invitation"
        title={t("list.emptyTitle")}
        description={t("list.emptyText")}
      />
    )
  const missing = selectedId !== null
  return (
    <InboxLayout
      label={t("list.label")}
      list={<InvitationList invitations={inbox.data} selectedId={selectedId} />}
      detail={
        selected === undefined ? (
          <EmptyState
            className={styles.placeholder}
            icon={missing ? "alert" : "invitation"}
            title={t(missing ? "detail.missingTitle" : "detail.pickTitle")}
            description={t(missing ? "detail.missingText" : "detail.pickText")}
          />
        ) : (
          <InvitationDetail invitation={selected} conversation={conversation(selected.id)} />
        )
      }
      selectedKey={selectedId}
      backTo="/candidate/invitations"
    />
  )
}
