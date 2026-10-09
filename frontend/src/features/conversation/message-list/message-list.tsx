import { useLayoutEffect, useRef } from "react"
import type { Message, Side } from "@/shared/api"
import { BackendText, useFormatters, useTranslation } from "@/shared/i18n"
import { Icon, ScrollArea } from "@/shared/ui"
import styles from "./message-list.module.css"

export interface MessageListProps {
  readonly messages: readonly Message[]
  readonly side: Side
}

function useFreshIds(messages: readonly Message[]): ReadonlySet<string> {
  const initial = useRef<ReadonlySet<string> | null>(null)
  if (initial.current === null) initial.current = new Set(messages.map((message) => message.id))
  return initial.current
}

function ReadMark({ message }: { readonly message: Message }) {
  const { t } = useTranslation("conversation")
  const read = message.read_at !== null
  return (
    <span className={styles.read} data-read={read}>
      <Icon name={read ? "accepted" : "check"} size="sm" />
      {read ? t("read") : t("delivered")}
    </span>
  )
}

export function MessageList({ messages, side }: MessageListProps) {
  const { t } = useTranslation("conversation")
  const format = useFormatters()
  const initial = useFreshIds(messages)
  const endRef = useRef<HTMLSpanElement | null>(null)
  const count = messages.length

  useLayoutEffect(() => {
    const viewport = endRef.current?.parentElement
    if (viewport === null || viewport === undefined || count === 0) return
    viewport.scrollTop = viewport.scrollHeight
  }, [count])

  return (
    <ScrollArea label={t("history")} className={styles.scroll}>
      <ol className={styles.list}>
        {messages.map((message) => {
          const own = message.author === side
          return (
            <li
              key={message.id}
              className={styles.item}
              data-own={own}
              data-fresh={!initial.has(message.id)}
            >
              <span className="visually-hidden">
                {own ? t("you") : t(`author.${message.author}`)}
              </span>
              <BackendText as="p" className={styles.bubble}>
                {message.text}
              </BackendText>
              <span className={styles.meta}>
                <time dateTime={message.sent_at}>{format.dateTime(message.sent_at)}</time>
                {own ? <ReadMark message={message} /> : null}
              </span>
            </li>
          )
        })}
      </ol>
      <span ref={endRef} aria-hidden="true" />
    </ScrollArea>
  )
}
