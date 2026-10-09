import { clsx } from "clsx"
import { type KeyboardEvent, type ReactNode, useId } from "react"
import { useInputModality, useSlidingIndicator } from "../../../motion"
import { Icon, type IconName } from "../../primitives/icon/icon"
import styles from "./tabs.module.css"

export interface TabItem<T extends string> {
  readonly value: T
  readonly label: string
  readonly icon?: IconName | undefined
  readonly count?: number | undefined
}

export interface TabsProps<T extends string> {
  readonly label: string
  readonly tabs: readonly TabItem<T>[]
  readonly value: T
  readonly onChange: (value: T) => void
  readonly className?: string | undefined
  readonly children: ReactNode
}

const STEP: Readonly<Record<string, number>> = { ArrowRight: 1, ArrowLeft: -1 }

export function Tabs<T extends string>({
  label,
  tabs,
  value,
  onChange,
  className,
  children,
}: TabsProps<T>) {
  const id = useId()
  const modality = useInputModality()
  const { listRef, indicatorRef, itemRef } = useSlidingIndicator<HTMLDivElement>(value, {
    instant: modality.instant,
  })
  const index = tabs.findIndex((tab) => tab.value === value)

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    modality.onKeyDown()
    const last = tabs.length - 1
    const next =
      event.key === "Home"
        ? 0
        : event.key === "End"
          ? last
          : (index + (STEP[event.key] ?? 0) + tabs.length) % tabs.length
    const tab = tabs[next]
    if (tab === undefined || next === index) return
    event.preventDefault()
    onChange(tab.value)
    listRef.current?.querySelectorAll<HTMLButtonElement>("[role=tab]")[next]?.focus()
  }

  return (
    <div className={clsx(styles.tabs, className)}>
      <div
        ref={listRef}
        role="tablist"
        aria-label={label}
        className={styles.list}
        onKeyDown={onKeyDown}
        onPointerDown={modality.onPointerDown}
      >
        <span ref={indicatorRef} className={styles.indicator} aria-hidden="true" />
        {tabs.map((tab) => (
          <button
            key={tab.value}
            ref={itemRef(tab.value)}
            type="button"
            role="tab"
            id={`${id}-${tab.value}`}
            aria-selected={tab.value === value}
            aria-controls={`${id}-panel`}
            tabIndex={tab.value === value ? 0 : -1}
            className={styles.tab}
            onClick={() => onChange(tab.value)}
          >
            {tab.icon === undefined ? null : <Icon name={tab.icon} size="sm" />}
            <span>{tab.label}</span>
            {tab.count === undefined ? null : <span className={styles.count}>{tab.count}</span>}
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        id={`${id}-panel`}
        aria-labelledby={`${id}-${value}`}
        className={styles.panel}
      >
        {children}
      </div>
    </div>
  )
}
