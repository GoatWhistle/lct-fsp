import { type KeyboardEvent, useEffect, useId, useMemo, useRef, useState } from "react"
import { useTranslation } from "react-i18next"
import { Chip } from "../../data-display/chip/chip"
import { ScrollArea } from "../../layout/scroll-area/scroll-area"
import { Popover } from "../../overlays/popover/popover"
import { useListNavigation } from "../../overlays/popover/use-list-navigation"
import { Icon } from "../../primitives/icon/icon"
import { Field } from "../field/field"
import styles from "./combobox.module.css"

const VISIBLE_LIMIT = 60

export interface ComboboxOption {
  readonly value: string
  readonly label: string
  readonly hint?: string | undefined
}

export interface ComboboxProps {
  readonly label: string
  readonly values: readonly string[]
  readonly options: readonly ComboboxOption[]
  readonly onChange: (values: readonly string[]) => void
  readonly max?: number | undefined
  readonly placeholder?: string | undefined
  readonly hint?: string | undefined
  readonly error?: string | undefined
  readonly disabled?: boolean | undefined
  readonly className?: string | undefined
}

function filtered(options: readonly ComboboxOption[], values: readonly string[], query: string) {
  const needle = query.trim().toLocaleLowerCase()
  const free = options.filter((option) => !values.includes(option.value))
  const hits =
    needle === ""
      ? free
      : free.filter((option) => option.label.toLocaleLowerCase().includes(needle))
  return hits.slice(0, VISIBLE_LIMIT)
}

export function Combobox({
  label,
  values,
  options,
  onChange,
  max,
  placeholder,
  hint,
  error,
  disabled = false,
  className,
}: ComboboxProps) {
  const { t } = useTranslation()
  const [query, setQuery] = useState("")
  const [open, setOpen] = useState(false)
  const [announcement, setAnnouncement] = useState("")
  const frameRef = useRef<HTMLDivElement | null>(null)
  const inputRef = useRef<HTMLInputElement | null>(null)
  const listId = useId()
  const byValue = useMemo(() => new Map(options.map((o) => [o.value, o])), [options])
  const visible = useMemo(() => filtered(options, values, query), [options, values, query])
  const navigation = useListNavigation(visible)
  const full = max !== undefined && values.length >= max
  const optionId = (index: number) => `${listId}-${index}`

  useEffect(() => {
    navigation.setActiveIndex(visible.length > 0 ? 0 : -1)
  }, [visible, navigation.setActiveIndex])

  const add = (option: ComboboxOption | undefined) => {
    if (option === undefined || full) return
    onChange([...values, option.value])
    setAnnouncement(t("combobox.added", { label: option.label }))
    setQuery("")
  }
  const remove = (value: string) => {
    onChange(values.filter((item) => item !== value))
    setAnnouncement(t("combobox.removed", { label: byValue.get(value)?.label ?? value }))
    inputRef.current?.focus()
  }
  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter" && open) {
      event.preventDefault()
      add(visible[navigation.activeIndex])
    } else if (event.key === "Backspace" && query === "" && values.length > 0) {
      remove(values[values.length - 1] ?? "")
    } else if (event.key === "Escape") {
      setOpen(false)
    } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault()
      setOpen(true)
      navigation.handleKey(event.key)
    }
  }

  return (
    <Field label={label} hint={hint} error={error} className={className}>
      {(control, meta) => (
        <>
          <div
            ref={frameRef}
            className={styles.frame}
            data-disabled={disabled}
            data-open={open}
            onPointerDown={(event) => {
              if (event.target === event.currentTarget) event.preventDefault()
              inputRef.current?.focus()
            }}
          >
            {values.map((value) => (
              <Chip key={value} onRemove={disabled ? undefined : () => remove(value)}>
                {byValue.get(value)?.label ?? value}
              </Chip>
            ))}
            <input
              {...control}
              ref={inputRef}
              className={styles.input}
              role="combobox"
              aria-autocomplete="list"
              aria-expanded={open}
              aria-controls={listId}
              aria-activedescendant={
                open && navigation.activeIndex >= 0 ? optionId(navigation.activeIndex) : undefined
              }
              value={query}
              disabled={disabled || full}
              placeholder={
                full ? t("combobox.limit", { max }) : (placeholder ?? t("combobox.placeholder"))
              }
              autoComplete="off"
              onChange={(event) => {
                setQuery(event.target.value)
                setOpen(true)
              }}
              onFocus={() => setOpen(true)}
              onBlur={() => setOpen(false)}
              onKeyDown={onKeyDown}
            />
            <Icon name="search" size="sm" className={styles.icon} />
          </div>
          {max === undefined ? null : (
            <span className={styles.count}>
              {t("combobox.selected", { count: values.length, max })}
            </span>
          )}
          <Popover
            open={open && !full}
            onClose={() => setOpen(false)}
            anchorRef={frameRef}
            matchAnchorWidth
            className={styles.popover}
          >
            <ScrollArea className={styles.scroller}>
              <div
                role="listbox"
                id={listId}
                aria-labelledby={meta.labelId}
                className={styles.list}
              >
                {visible.length === 0 ? (
                  <p className={styles.empty}>{t("combobox.empty")}</p>
                ) : (
                  visible.map((option, index) => (
                    <div
                      key={option.value}
                      id={optionId(index)}
                      role="option"
                      tabIndex={-1}
                      aria-selected={false}
                      className={styles.option}
                      data-active={index === navigation.activeIndex}
                      onPointerMove={() => navigation.setActiveIndex(index)}
                      onPointerDown={(event) => event.preventDefault()}
                      onClick={() => add(option)}
                      onKeyDown={() => undefined}
                    >
                      <span>{option.label}</span>
                      {option.hint === undefined ? null : (
                        <span className={styles.hint}>{option.hint}</span>
                      )}
                    </div>
                  ))
                )}
              </div>
            </ScrollArea>
          </Popover>
          <span className="visually-hidden" aria-live="polite">
            {announcement}
          </span>
        </>
      )}
    </Field>
  )
}
