import { useId, useState, type KeyboardEvent } from 'react'
import type { Technology } from '../api/client'

/** Стек из справочника технологий с автодополнением: ввод фильтрует справочник, стрелки и Enter выбирают. */
export function TechnologyPicker({
  technologies,
  selected,
  onChange,
}: {
  technologies: Technology[]
  selected: string[]
  onChange: (codes: string[]) => void
}) {
  const listId = useId()
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)

  const names = new Map(technologies.map((t) => [t.code, t.name]))
  const q = query.trim().toLowerCase()
  // Сначала — названия, которые начинаются с введённого, дальше по алфавиту без учёта регистра.
  const starts = (t: Technology) => Number(!t.name.toLowerCase().startsWith(q))
  const options = technologies
    .filter((t) => !selected.includes(t.code) && t.name.toLowerCase().includes(q))
    .sort((a, b) => starts(a) - starts(b) || a.name.localeCompare(b.name, 'ru', { sensitivity: 'base' }))
  const current = Math.min(active, options.length - 1)
  const expanded = open && options.length > 0

  function add(code: string) {
    onChange([...selected, code])
    setQuery('')
    setActive(0)
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setOpen(true)
      setActive(Math.min(current + 1, options.length - 1))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActive(Math.max(current - 1, 0))
    } else if (event.key === 'Enter' && expanded) {
      event.preventDefault()
      add(options[current].code)
    } else if (event.key === 'Escape') {
      setOpen(false)
    } else if (event.key === 'Backspace' && query === '' && selected.length > 0) {
      onChange(selected.slice(0, -1))
    }
  }

  return (
    <div className="combobox">
      {selected.length > 0 && (
        <ul className="chips">
          {selected.map((code) => (
            <li key={code} className="chip chip-removable">
              {names.get(code) ?? code}
              <button
                type="button"
                aria-label={`Убрать ${names.get(code) ?? code}`}
                onClick={() => onChange(selected.filter((c) => c !== code))}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
      <input
        role="combobox"
        aria-label="Добавить технологию"
        aria-autocomplete="list"
        aria-expanded={expanded}
        aria-controls={listId}
        aria-activedescendant={expanded ? `${listId}-${options[current].code}` : undefined}
        placeholder="Начните вводить: Python, PostgreSQL, Docker…"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value)
          setOpen(true)
          setActive(0)
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={onKeyDown}
      />
      {expanded && (
        <ul id={listId} role="listbox" className="combobox-list">
          {options.map((t, i) => (
            <li
              key={t.code}
              id={`${listId}-${t.code}`}
              role="option"
              aria-selected={i === current}
              className={i === current ? 'active' : undefined}
              // mousedown, а не click: иначе поле потеряет фокус и список закроется раньше выбора.
              onMouseDown={(e) => {
                e.preventDefault()
                add(t.code)
              }}
              onMouseEnter={() => setActive(i)}
            >
              {t.name}
            </li>
          ))}
        </ul>
      )}
      {open && q && options.length === 0 && <p className="hint">Такой технологии нет в справочнике</p>}
    </div>
  )
}
