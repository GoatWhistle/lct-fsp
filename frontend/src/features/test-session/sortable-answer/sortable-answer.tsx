import type { Option } from "@/shared/api"
import { useTranslation } from "@/shared/i18n"
import { SortableList } from "@/shared/ui"
import styles from "../../../shared/styles/layout.module.css"

export interface SortableAnswerProps {
  readonly options: readonly Option[]
  readonly order: readonly string[]
  readonly onChange: (order: readonly string[]) => void
}

function short(text: string): string {
  const limit = 40
  return text.length > limit ? `${text.slice(0, limit)}…` : text
}

export function SortableAnswer({ options, order, onChange }: SortableAnswerProps) {
  const { t } = useTranslation("test")
  const byLetter = new Map(options.map((option) => [option.letter, option]))
  const items = order.flatMap((letter) => {
    const option = byLetter.get(letter)
    return option === undefined
      ? []
      : [
          {
            id: letter,
            label: short(option.text),
            content: <span className={styles.preWrap}>{option.text}</span>,
          },
        ]
  })

  return (
    <SortableList
      label={t("answer.order")}
      hint={t("answer.orderHint")}
      items={items}
      onChange={(next) => onChange(next.map((item) => item.id))}
      messages={{
        picked: (item) => t("answer.picked", { item }),
        moved: (item, position) => t("answer.moved", { item, position }),
        dropped: (item, position) => t("answer.dropped", { item, position }),
      }}
    />
  )
}
