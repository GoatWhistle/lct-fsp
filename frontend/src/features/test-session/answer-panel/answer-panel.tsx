import { useEffect, useRef, useState } from "react"
import type { TestItem } from "@/shared/api"
import { useErrorText, useTranslation } from "@/shared/i18n"
import { Banner, Button, Form, Icon, Pane, TextField } from "@/shared/ui"
import { ChoiceAnswer } from "../choice-answer/choice-answer"
import { SortableAnswer } from "../sortable-answer/sortable-answer"
import styles from "./answer-panel.module.css"

export interface AnswerPanelProps {
  readonly item: TestItem
  readonly pending: boolean
  readonly error: unknown
  readonly onSubmit: (response: string) => void
}

function responseOf(
  item: TestItem,
  choice: string | null,
  order: readonly string[],
  value: string,
) {
  if (item.answer_format === "choice") return choice ?? ""
  if (item.answer_format === "ordering") return order.join("")
  return value.trim()
}

function useEnterSubmit(submit: () => void, enabled: boolean) {
  const latest = useRef(submit)
  latest.current = submit
  useEffect(() => {
    if (!enabled) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Enter" || event.repeat || event.defaultPrevented) return
      const target = event.target
      if (target instanceof HTMLElement && target.closest("button, a, textarea, input") !== null) {
        return
      }
      event.preventDefault()
      latest.current()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [enabled])
}

export function AnswerPanel({ item, pending, error, onSubmit }: AnswerPanelProps) {
  const { t } = useTranslation("test")
  const errorText = useErrorText()
  const [choice, setChoice] = useState<string | null>(null)
  const [order, setOrder] = useState<readonly string[]>(() => item.options.map((o) => o.letter))
  const [value, setValue] = useState("")
  const response = responseOf(item, choice, order, value)
  const ready = response !== "" && !pending
  const last = item.number >= item.max_items
  const submit = () => {
    if (ready) onSubmit(response)
  }
  useEnterSubmit(submit, item.answer_format !== "value")

  return (
    <Pane
      title={t("answerTitle")}
      meta={
        <p className={styles.format}>
          {item.answer_format === "choice"
            ? t("answer.choice")
            : item.answer_format === "ordering"
              ? t("answer.order")
              : t("answer.valueTitle")}
        </p>
      }
    >
      <Form onSubmit={submit} className={styles.form}>
        {item.answer_format === "choice" && (
          <ChoiceAnswer
            options={item.options}
            value={choice}
            onChange={setChoice}
            disabled={pending}
          />
        )}
        {item.answer_format === "ordering" && (
          <SortableAnswer options={item.options} order={order} onChange={setOrder} />
        )}
        {item.answer_format === "value" && (
          <TextField
            label={t("answer.value")}
            hideLabel
            value={value}
            onChange={setValue}
            placeholder={t("answer.valuePlaceholder")}
            autoComplete="off"
            disabled={pending}
            className={styles.value}
          />
        )}
        {error === null ? null : <Banner tone="critical" title={errorText(error)} />}
        <footer className={styles.foot}>
          <Button
            type="submit"
            icon={last ? "check" : "arrow-right"}
            iconPosition="end"
            disabled={!ready}
            pending={pending}
            pendingLabel={t("answer.pending")}
          >
            {last ? t("answer.finish") : t("answer.submit")}
          </Button>
          {item.answer_format === "choice" && (
            <span className={styles.keys}>
              <Icon name="keyboard" size="sm" />
              {t("intro.keys")}
            </span>
          )}
        </footer>
      </Form>
    </Pane>
  )
}
