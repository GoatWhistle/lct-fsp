import { type KeyboardEvent, type ReactNode, useRef, useState } from "react"
import { Icon } from "../../primitives/icon/icon"
import styles from "./sortable-list.module.css"
import { useSortableDrag } from "./use-sortable-drag"

export interface SortableItem {
  readonly id: string
  readonly label: string
  readonly content: ReactNode
}

export interface SortableMessages {
  readonly picked: (label: string) => string
  readonly moved: (label: string, position: number) => string
  readonly dropped: (label: string, position: number) => string
}

export interface SortableListProps {
  readonly label: string
  readonly hint: string
  readonly items: readonly SortableItem[]
  readonly onChange: (items: readonly SortableItem[]) => void
  readonly messages: SortableMessages
}

const TOGGLE_KEYS = new Set([" ", "Enter"])
const MOVE_KEYS: Readonly<Record<string, number>> = { ArrowUp: -1, ArrowDown: 1 }

function moved<Item>(list: readonly Item[], from: number, to: number): Item[] {
  const next = [...list]
  const [item] = next.splice(from, 1)
  if (item !== undefined) next.splice(to, 0, item)
  return next
}

export function SortableList({ label, hint, items, onChange, messages }: SortableListProps) {
  const listRef = useRef<HTMLOListElement | null>(null)
  const [picked, setPicked] = useState<string | null>(null)
  const [announcement, setAnnouncement] = useState("")
  const drag = useSortableDrag(listRef, (from, to) => onChange(moved(items, from, to)))

  const focusRow = (index: number) => {
    window.requestAnimationFrame(() => {
      listRef.current?.querySelectorAll<HTMLButtonElement>("button")[index]?.focus()
    })
  }

  const toggle = (item: SortableItem, index: number) => {
    const pick = picked !== item.id
    setPicked(pick ? item.id : null)
    setAnnouncement(pick ? messages.picked(item.label) : messages.dropped(item.label, index + 1))
  }

  const shift = (item: SortableItem, index: number, to: number) => {
    onChange(moved(items, index, to))
    setAnnouncement(messages.moved(item.label, to + 1))
    focusRow(to)
  }

  const onKeyDown = (index: number) => (event: KeyboardEvent<HTMLButtonElement>) => {
    const item = items[index]
    if (item === undefined) return
    if (TOGGLE_KEYS.has(event.key)) {
      event.preventDefault()
      toggle(item, index)
      return
    }
    const to = index + (MOVE_KEYS[event.key] ?? 0)
    if (picked !== item.id || to === index || to < 0 || to >= items.length) return
    event.preventDefault()
    shift(item, index, to)
  }

  return (
    <div className={styles.sortable}>
      <p className={styles.hint} id={`${label}-hint`}>
        {hint}
      </p>
      <ol ref={listRef} className={styles.list} aria-label={label}>
        {items.map((item, index) => (
          <li
            key={item.id}
            className={styles.row}
            data-dragging={drag.dragging === index}
            data-picked={picked === item.id}
          >
            <button
              type="button"
              className={styles.handle}
              aria-pressed={picked === item.id}
              aria-describedby={`${label}-hint`}
              onKeyDown={onKeyDown(index)}
              onPointerDown={drag.start(index)}
              onPointerMove={drag.move}
              onPointerUp={drag.end}
              onPointerCancel={drag.end}
            >
              <span className={styles.position}>{index + 1}</span>
              <span className={styles.content}>{item.content}</span>
              <Icon name="grip" size="md" className={styles.grip} />
            </button>
          </li>
        ))}
      </ol>
      <p className="visually-hidden" aria-live="assertive">
        {announcement}
      </p>
    </div>
  )
}
