import { useState, type FormEvent } from 'react'
import { api, errorMessage, type CandidatePath } from '../api/client'
import { type Catalog } from './catalog'

const hints: Record<string, string> = {
  intern: 'учусь, первые проекты',
  junior: 'решаю задачи под присмотром',
  middle: 'веду задачи сам',
  senior: 'отвечаю за решения и систему',
}

type Props = {
  catalog: Catalog
  survey: NonNullable<CandidatePath['survey']>
  onDone: (path: CandidatePath) => void
  onChangeSurvey: () => void
}

/** Выбор грейда: кандидат заявляет его сам, тест проверяет. */
export function GradeStep({ catalog, survey, onDone, onChangeSurvey }: Props) {
  const [grade, setGrade] = useState(catalog.grades[1]?.code ?? catalog.grades[0]?.code ?? '')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const chosen = catalog.grades.find((g) => g.code === grade)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    const { data, error } = await api.POST('/api/candidate/path/attempts', { body: { grade } })
    setSubmitting(false)
    if (data) onDone(data)
    else setError(errorMessage(error))
  }

  return (
    <form onSubmit={submit} className="card form">
      <h2>Грейд</h2>
      <p className="muted">
        {survey.specialization.name}.{' '}
        <button type="button" className="link-button" onClick={onChangeSurvey}>
          Изменить
        </button>
      </p>
      <fieldset className="choice-grid">
        <legend>На какой грейд вы претендуете?</legend>
        {catalog.grades.map((g) => (
          <label key={g.code} className={grade === g.code ? 'role-option selected' : 'role-option'}>
            <input
              type="radio"
              name="grade"
              value={g.code}
              checked={grade === g.code}
              onChange={() => setGrade(g.code)}
            />
            <strong>{g.name}</strong>
            <span className="muted">{hints[g.code]}</span>
          </label>
        ))}
      </fieldset>
      <p className="hint">
        Тест обязателен: категорию определяет только он. Задания у каждого свои, ответы проверяет
        сервер, время ответа записывается. Если уверенности для выбранного грейда не хватит, сразу
        предложим продолжить на грейд ниже — ответы засчитаются.
      </p>
      {error && <p className="error">{error}</p>}
      <div className="actions">
        <button type="submit" className="button" disabled={submitting || !chosen}>
          Начать тест{chosen ? ` на ${chosen.name}` : ''}
        </button>
      </div>
    </form>
  )
}
