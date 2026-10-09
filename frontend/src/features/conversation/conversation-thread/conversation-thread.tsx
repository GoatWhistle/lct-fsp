import { clsx } from "clsx"
import type { Side } from "@/shared/api"
import { useTranslation } from "@/shared/i18n"
import { EmptyState, LoadError, Skeleton } from "@/shared/ui"
import { Composer } from "../composer/composer"
import { MessageList } from "../message-list/message-list"
import { useMessages } from "../messages.queries"
import styles from "./conversation-thread.module.css"

export interface ConversationThreadProps {
  readonly invitationId: string
  readonly side: Side
  readonly className?: string | undefined
}

function ThreadBody({ invitationId, side }: ConversationThreadProps) {
  const { t } = useTranslation("conversation")
  const messages = useMessages(side, invitationId)
  if (messages.isError && messages.data === undefined)
    return (
      <div className={styles.state}>
        <LoadError
          error={messages.error}
          onRetry={() => void messages.refetch()}
          pending={messages.isFetching}
        />
      </div>
    )
  if (messages.data === undefined)
    return (
      <div className={styles.state}>
        <Skeleton lines={3} />
      </div>
    )
  if (messages.data.length === 0)
    return (
      <div className={styles.state}>
        <EmptyState
          icon="message"
          title={t("empty.title")}
          description={t(`empty.${side}` as never)}
        />
      </div>
    )
  return <MessageList messages={messages.data} side={side} />
}

export function ConversationThread({ invitationId, side, className }: ConversationThreadProps) {
  const { t } = useTranslation("conversation")
  return (
    <section className={clsx(styles.thread, className)} aria-label={t("label")}>
      <ThreadBody invitationId={invitationId} side={side} />
      <Composer invitationId={invitationId} side={side} />
    </section>
  )
}
