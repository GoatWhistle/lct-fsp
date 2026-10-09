import { type KeyboardEvent, useState } from "react"
import type { Side } from "@/shared/api"
import { useErrorText, useTranslation } from "@/shared/i18n"
import { Button, Form, TextArea } from "@/shared/ui"
import { useSendMessage } from "../messages.queries"
import styles from "./composer.module.css"

const MAX_LENGTH = 4000

export interface ComposerProps {
  readonly invitationId: string
  readonly side: Side
}

export function Composer({ invitationId, side }: ComposerProps) {
  const { t } = useTranslation("conversation")
  const errorText = useErrorText()
  const send = useSendMessage(side, invitationId)
  const [text, setText] = useState("")
  const ready = text.trim() !== ""

  const submit = () => {
    if (!ready || send.isPending) return
    send.mutate(text.trim(), { onSuccess: () => setText("") })
  }
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) return
    event.preventDefault()
    submit()
  }

  return (
    <Form onSubmit={submit} className={styles.composer}>
      <TextArea
        label={t("composer.label")}
        hideLabel
        value={text}
        onChange={setText}
        onKeyDown={onKeyDown}
        placeholder={t("composer.placeholder")}
        maxLength={MAX_LENGTH}
        minRows={1}
        error={send.isError ? errorText(send.error) : undefined}
        className={styles.field}
      />
      <Button
        type="submit"
        icon="send"
        disabled={!ready}
        pending={send.isPending}
        className={styles.send}
      >
        {t("composer.send")}
      </Button>
      <p className={styles.hint}>{t("composer.hint")}</p>
    </Form>
  )
}
