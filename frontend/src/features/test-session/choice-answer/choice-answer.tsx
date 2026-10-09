import { useEffect } from "react"
import type { Option } from "@/shared/api"
import { useTranslation } from "@/shared/i18n"
import { RadioGroup } from "@/shared/ui"
import styles from "../../../shared/styles/layout.module.css"

const MAX_SHORTCUT = 9

export interface ChoiceAnswerProps {
  readonly options: readonly Option[]
  readonly value: string | null
  readonly onChange: (letter: string) => void
  readonly disabled: boolean
}

function isTyping(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLElement &&
    (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName))
  )
}

export function ChoiceAnswer({ options, value, onChange, disabled }: ChoiceAnswerProps) {
  const { t } = useTranslation("test")

  useEffect(() => {
    if (disabled) return
    const onKey = (event: KeyboardEvent) => {
      if (event.altKey || event.ctrlKey || event.metaKey || isTyping(event.target)) return
      const digit = Number.parseInt(event.key, 10)
      if (Number.isNaN(digit) || digit < 1 || digit > MAX_SHORTCUT) return
      const option = options[digit - 1]
      if (option === undefined) return
      event.preventDefault()
      onChange(option.letter)
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [options, onChange, disabled])

  return (
    <RadioGroup
      label={t("answer.choice")}
      hideLabel
      appearance="card"
      value={value}
      onChange={onChange}
      disabled={disabled}
      options={options.map((option, index) => ({
        value: option.letter,
        label: <span className={styles.preWrap}>{option.text}</span>,
        shortcut: index < MAX_SHORTCUT ? String(index + 1) : undefined,
      }))}
    />
  )
}
