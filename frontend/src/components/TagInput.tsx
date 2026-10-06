import { useState, type KeyboardEvent } from 'react'

/** Короткие метки свободным текстом: Enter или запятая добавляют, × убирает. Повторы без учёта регистра не добавляются. */
export function TagInput({
  tags,
  onChange,
  max,
  maxLength,
  label,
  placeholder,
}: {
  tags: string[]
  onChange: (tags: string[]) => void
  max: number
  maxLength: number
  label: string
  placeholder?: string
}) {
  const [value, setValue] = useState('')
  const full = tags.length >= max

  function commit() {
    const tag = value.trim()
    if (tag && !full && !tags.some((t) => t.toLowerCase() === tag.toLowerCase())) onChange([...tags, tag])
    setValue('')
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter' || event.key === ',') {
      event.preventDefault()
      commit()
    } else if (event.key === 'Backspace' && value === '' && tags.length > 0) {
      onChange(tags.slice(0, -1))
    }
  }

  return (
    <div className="tag-input">
      {tags.length > 0 && (
        <ul className="chips">
          {tags.map((tag) => (
            <li key={tag} className="chip chip-removable">
              {tag}
              <button type="button" aria-label={`Убрать «${tag}»`} onClick={() => onChange(tags.filter((t) => t !== tag))}>
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
      <input
        aria-label={label}
        maxLength={maxLength}
        disabled={full}
        placeholder={full ? `Не больше ${max}` : placeholder}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={onKeyDown}
        onBlur={commit}
      />
    </div>
  )
}
