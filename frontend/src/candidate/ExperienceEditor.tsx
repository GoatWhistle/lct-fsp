import { useState } from 'react'
import type { Technology } from '../api/client'
import { TechnologyPicker } from '../components/TechnologyPicker'
import { emptyEntry, thisMonth, type EntryDraft } from './experience'

// Лимиты — как `experience_*` в механиках бэкенда; бэкенд проверяет их сам.
const ENTRIES_MAX = 20
const LINE_MAX = 200
const SUMMARY_MAX = 2000

/** Правка карточки опыта: записи добавляются, правятся и удаляются; годы по технологиям считает бэкенд. */
export function ExperienceEditor({
  entries,
  technologies,
  onChange,
}: {
  entries: EntryDraft[]
  technologies: Technology[]
  onChange: (entries: EntryDraft[]) => void
}) {
  // Начало записи — не в будущем: месяц открытия формы по местному времени.
  const [maxStart] = useState(thisMonth)

  function update(index: number, changes: Partial<EntryDraft>) {
    onChange(entries.map((e, i) => (i === index ? { ...e, ...changes } : e)))
  }

  return (
    <div className="stack">
      {entries.map((entry, i) => (
        <fieldset key={entry.key} className="plain experience-entry">
          <legend className="visually-hidden">Запись опыта {i + 1}</legend>
          <div className="field-row">
            <label className="field">
              Компания или проект
              <input
                required
                maxLength={LINE_MAX}
                value={entry.place}
                onChange={(e) => update(i, { place: e.target.value })}
              />
            </label>
            <label className="field">
              Роль
              <input maxLength={LINE_MAX} value={entry.role} onChange={(e) => update(i, { role: e.target.value })} />
            </label>
          </div>
          <div className="field-row">
            <label className="field">
              Начало
              <input
                type="month"
                required
                max={maxStart}
                value={entry.start}
                onChange={(e) => update(i, { start: e.target.value })}
              />
            </label>
            <label className="field">
              Конец
              <input
                type="month"
                min={entry.start || undefined}
                value={entry.end}
                onChange={(e) => update(i, { end: e.target.value })}
              />
              <span className="hint">Пусто — по сейчас</span>
            </label>
          </div>
          <div className="field">
            <span>Технологии</span>
            <TechnologyPicker
              technologies={technologies}
              selected={entry.stack}
              onChange={(stack) => update(i, { stack })}
            />
          </div>
          <label className="field">
            Что делали
            <textarea
              rows={3}
              maxLength={SUMMARY_MAX}
              value={entry.summary}
              onChange={(e) => update(i, { summary: e.target.value })}
            />
          </label>
          <div className="actions">
            <button
              type="button"
              className="button button-small button-secondary"
              onClick={() => onChange(entries.filter((_, j) => j !== i))}
            >
              Удалить запись
            </button>
          </div>
        </fieldset>
      ))}
      {entries.length < ENTRIES_MAX && (
        <div className="actions">
          <button
            type="button"
            className="button button-small button-secondary"
            onClick={() => onChange([...entries, emptyEntry()])}
          >
            Добавить место работы или проект
          </button>
        </div>
      )}
    </div>
  )
}
