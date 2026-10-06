import { useState, type FormEvent } from 'react'
import { api, errorMessage, type CandidatePath } from '../api/client'
import type { Catalog } from './catalog'

type Props = {
  catalog: Catalog
  current: CandidatePath['survey']
  onDone: (path: CandidatePath) => void
  onCancel?: () => void
}

/** Опрос: отрасль и специализация. Специализации без готового теста видны, но недоступны. */
export function SurveyStep({ catalog, current, onDone, onCancel }: Props) {
  const firstWithTest = catalog.specializations.find((s) => s.has_test)?.code ?? ''
  const [industry, setIndustry] = useState(current?.industry.code ?? catalog.industries[0]?.code ?? '')
  const [specialization, setSpecialization] = useState(current?.specialization.code ?? firstWithTest)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    const { data, error } = await api.POST('/api/candidate/path/survey', {
      body: { industry, specialization },
    })
    setSubmitting(false)
    if (data) onDone(data)
    else setError(errorMessage(error))
  }

  return (
    <form onSubmit={submit} className="card form">
      <h2>Опрос</h2>
      <label className="field">
        Отрасль, в которой хотите работать
        <select value={industry} onChange={(e) => setIndustry(e.target.value)} required>
          {catalog.industries.map((i) => (
            <option key={i.code} value={i.code}>
              {i.name}
            </option>
          ))}
        </select>
        <span className="hint">На категорию не влияет — помогает работодателям вас найти</span>
      </label>
      <fieldset className="choice-grid">
        <legend>Специализация</legend>
        {catalog.specializations.map((s) => (
          <label
            key={s.code}
            className={[
              'role-option',
              specialization === s.code ? 'selected' : '',
              s.has_test ? '' : 'unavailable',
            ].join(' ')}
          >
            <input
              type="radio"
              name="specialization"
              value={s.code}
              checked={specialization === s.code}
              disabled={!s.has_test}
              onChange={() => setSpecialization(s.code)}
            />
            <strong>{s.name}</strong>
            <span className="muted">{s.has_test ? `${s.topics.length} тем` : 'тест готовится'}</span>
          </label>
        ))}
      </fieldset>
      {error && <p className="error">{error}</p>}
      <div className="actions">
        <button type="submit" className="button" disabled={submitting || !specialization}>
          Дальше — выбор грейда
        </button>
        {onCancel && (
          <button type="button" className="link-button" onClick={onCancel}>
            Отмена
          </button>
        )}
      </div>
    </form>
  )
}
