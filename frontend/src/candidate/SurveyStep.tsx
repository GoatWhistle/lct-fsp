import { useState, type FormEvent } from 'react'
import { api, errorMessage, type CandidatePath } from '../api/client'
import type { Catalog } from './catalog'

type Props = {
  catalog: Catalog
  current: CandidatePath['survey']
  onDone: (path: CandidatePath) => void
  onCancel?: () => void
}

/**
 * Опрос: направление — специализация («отрасль» в ТЗ). Специализации без готового теста видны, но
 * недоступны. Интересные сферы бизнеса — необязательная часть профиля, не опроса.
 */
export function SurveyStep({ catalog, current, onDone, onCancel }: Props) {
  const firstWithTest = catalog.specializations.find((s) => s.has_test)?.code ?? ''
  const [specialization, setSpecialization] = useState(current?.specialization.code ?? firstWithTest)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    const { data, error } = await api.POST('/api/candidate/path/survey', {
      body: { specialization },
    })
    setSubmitting(false)
    if (data) onDone(data)
    else setError(errorMessage(error))
  }

  return (
    <form onSubmit={submit} className="card form">
      <h2>Опрос</h2>
      <fieldset className="choice-grid">
        <legend>Направление, в котором хотите работать</legend>
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
      <p className="hint">
        По направлению строится тест и ваша категория. Интересные сферы бизнеса — финтех, госсектор и
        другие — можно отметить в профиле, по желанию.
      </p>
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
