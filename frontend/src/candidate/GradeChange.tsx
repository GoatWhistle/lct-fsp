import { useState } from 'react'
import { api, errorCode, errorMessage, type CandidatePath, type HistoryEntry } from '../api/client'
import { gradeName, type Catalog } from './catalog'
import { FocusConsent } from './protection'
import { dateTimeWords, dateWords, levelWords, thetaWithError } from './words'

type Props = { catalog: Catalog; path: CandidatePath; onChange: (path: CandidatePath) => void }

/** Ошибка API словами; у правила ожидания — с датой, когда можно. */
function failure(error: unknown): string {
  if (errorCode(error) === 'grade_change_too_early' && error && typeof error === 'object') {
    const at = 'available_at' in error && typeof error.available_at === 'string' ? error.available_at : null
    if (at) return `Попытка вверх станет доступна ${dateTimeWords(at)}.`
  }
  return errorMessage(error)
}

/**
 * Смена грейда. Вверх — тест с чистого листа: категория меняется, только если грейд подтверждён,
 * провал её не меняет. Вниз — сразу, без теста; это смена, после неё вверх — через срок ожидания.
 */
export function GradeChangeCard({ catalog, path, onChange }: Props) {
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [consent, setConsent] = useState(false)
  const up = path.grade_up
  const down = path.grade_down

  if (!up && !down) return null

  async function act(request: () => Promise<{ data?: CandidatePath; error?: unknown }>) {
    setSubmitting(true)
    setError(null)
    const { data, error } = await request()
    setSubmitting(false)
    if (data) onChange(data)
    else setError(failure(error))
  }

  function goUp() {
    if (!up) return
    act(() => api.POST('/api/candidate/path/attempts', { body: { grade: up.grade, focus_consent: consent } }))
  }

  function goDown() {
    if (!down) return
    const sure = window.confirm(
      `Перейти на ${gradeName(catalog, down)}? Теста не будет, категория сменится сразу. ` +
        'Вернуться выше можно будет только тестом и не раньше срока ожидания.',
    )
    if (sure) act(() => api.POST('/api/candidate/path/step-down'))
  }

  return (
    <div className="card form">
      <h2>Смена грейда</h2>
      {up && (
        <>
          <p>
            Тест на {gradeName(catalog, up.grade)} — новое измерение с чистого листа. Категория
            сменится, только если грейд подтвердится; если нет — останется прежней.
          </p>
          {up.available_at && (
            <p className="hint">Попытка вверх станет доступна {dateTimeWords(up.available_at)}.</p>
          )}
          <FocusConsent checked={consent} onChange={setConsent} />
        </>
      )}
      {error && <p className="error">{error}</p>}
      <div className="actions">
        {up && (
          <button
            type="button"
            className="button"
            disabled={submitting || up.available_at !== null}
            onClick={goUp}
          >
            Пройти на грейд выше — {gradeName(catalog, up.grade)}
          </button>
        )}
        {down && (
          <button type="button" className="button button-secondary" disabled={submitting} onClick={goDown}>
            Перейти на грейд ниже — {gradeName(catalog, down)}
          </button>
        )}
      </div>
    </div>
  )
}

function outcomeWords(catalog: Catalog, entry: HistoryEntry): string {
  const grade = (code: string | null | undefined) => gradeName(catalog, code ?? '')
  if (entry.event === 'step_down') return 'Переход вниз без теста'
  switch (entry.outcome) {
    case 'assigned':
      if (entry.purpose === 'grade_up') return 'Грейд повышен'
      return entry.outcome_grade === entry.grade
        ? 'Грейд подтверждён'
        : `Присвоен ${grade(entry.outcome_grade)}`
    case 'offered':
      return `Не хватило уверенности — дотест на ${grade(entry.outcome_grade)}`
    case 'no_category':
      return 'Категория не присвоена'
    case 'not_passed':
      return 'Не подтвердился — категория прежняя'
    case 'verification':
      return `Ждёт проверочного блока на ${grade(entry.outcome_grade)}`
    default:
      return ''
  }
}

/** История тестов и переходов: дата, грейд, уровень с погрешностью, итог. */
export function HistoryView({ catalog, history }: { catalog: Catalog; history: HistoryEntry[] }) {
  if (history.length === 0) return null
  return (
    <div className="card">
      <h2>История тестов и переходов</h2>
      <table className="table">
        <thead>
          <tr>
            <th scope="col">Дата</th>
            <th scope="col">Грейд</th>
            <th scope="col">Уровень</th>
            <th scope="col">Итог</th>
          </tr>
        </thead>
        <tbody>
          {history.map((entry, i) => (
            <tr key={i}>
              <td>{dateWords(entry.at)}</td>
              <th scope="row">{gradeName(catalog, entry.grade)}</th>
              <td>
                {entry.overall ? (
                  <>
                    {levelWords(entry.overall.band)}{' '}
                    <span className="muted">({thetaWithError(entry.overall)})</span>
                  </>
                ) : (
                  <span className="muted">—</span>
                )}
              </td>
              <td>{outcomeWords(catalog, entry)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
