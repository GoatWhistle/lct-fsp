import { useCallback, useEffect, useState } from 'react'
import { api, errorMessage, type Application, type Vacancy } from '../api/client'
import { salaryWords } from '../components/salary'
import { applicationStatusWords, isOpen, vacancyTermsWords } from '../vacancy/words'
import { useCatalog } from './catalog'
import { dateTimeWords, dateWords } from './words'

/**
 * Вакансии компаний и свои отклики. Откликнуться можно и без категории — это своя инициатива:
 * компания вакансии сразу увидит имя, контакты и профиль, кроме ожидаемой зарплаты. Доступ можно
 * отозвать.
 */
export function Vacancies() {
  const { catalog } = useCatalog()
  const [specialization, setSpecialization] = useState('')
  const [vacancies, setVacancies] = useState<Vacancy[] | null>(null)
  const [applications, setApplications] = useState<Application[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const loadApplications = useCallback(() => {
    api.GET('/api/candidate/applications').then(({ data, error }) => {
      if (data) setApplications(data)
      else setError(errorMessage(error))
    })
  }, [])

  useEffect(loadApplications, [loadApplications])

  useEffect(() => {
    // Ответ по прошлому фильтру, пришедший позже, список не перетирает.
    let stale = false
    api
      .GET('/api/candidate/vacancies', { params: { query: specialization ? { specialization } : {} } })
      .then(({ data, error }) => {
        if (stale) return
        if (data) setVacancies(data)
        else setError(errorMessage(error))
      })
    return () => {
      stale = true
    }
  }, [specialization])

  function replace(next: Application) {
    setApplications((current) => current?.map((a) => (a.id === next.id ? next : a)) ?? null)
  }

  if (error) return <p className="error">Вакансии не загрузились: {error}</p>
  if (!vacancies || !applications) return null
  const appliedTo = new Set(applications.map((a) => a.vacancy_id))
  return (
    <section className="stack">
      <div className="section-head">
        <h2>Вакансии</h2>
        {catalog && (
          <select value={specialization} onChange={(e) => setSpecialization(e.target.value)} aria-label="Специализация">
            <option value="">Все специализации</option>
            {catalog.specializations.map((s) => (
              <option key={s.code} value={s.code}>
                {s.name}
              </option>
            ))}
          </select>
        )}
      </div>
      {vacancies.length === 0 ? (
        <div className="card">
          <p>Опубликованных вакансий пока нет.</p>
        </div>
      ) : (
        vacancies.map((v) => (
          <VacancyCard
            key={v.id}
            vacancy={v}
            applied={appliedTo.has(v.id)}
            onApplied={(a) => setApplications((current) => [a, ...(current ?? [])])}
          />
        ))
      )}
      {applications.length > 0 && (
        <>
          <h2>Мои отклики</h2>
          <div className="card">
            <ul className="selection-list">
              {applications.map((a) => (
                <OwnApplication key={a.id} application={a} onChange={replace} onRevoked={loadApplications} />
              ))}
            </ul>
          </div>
        </>
      )}
    </section>
  )
}

function VacancyCard({
  vacancy,
  applied,
  onApplied,
}: {
  vacancy: Vacancy
  applied: boolean
  onApplied: (application: Application) => void
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function apply() {
    setBusy(true)
    setError(null)
    const { data, error } = await api.POST('/api/candidate/vacancies/{vacancy_id}/apply', {
      params: { path: { vacancy_id: vacancy.id } },
    })
    setBusy(false)
    if (data) onApplied(data)
    else setError(errorMessage(error))
  }

  return (
    <article className="card need-card">
      <span className="muted">{vacancy.company_name}</span>
      <h3>{vacancy.title}</h3>
      <p className="muted">{vacancyTermsWords(vacancy)}</p>
      {vacancy.description && <p className="prewrap">{vacancy.description}</p>}
      {applied ? (
        <p className="success">Вы откликнулись — статус в «Моих откликах».</p>
      ) : (
        <>
          <p className="hint">
            Компания увидит ваше имя, контакты и профиль сразу после отклика. Ожидаемую зарплату она не увидит.
          </p>
          <div className="actions">
            <button type="button" className="button button-small" disabled={busy} onClick={apply}>
              Откликнуться
            </button>
          </div>
        </>
      )}
      {error && <p className="error">{error}</p>}
    </article>
  )
}

function OwnApplication({
  application,
  onChange,
  onRevoked,
}: {
  application: Application
  onChange: (application: Application) => void
  /** Отзыв закрывает все отклики компании — перечитать список. */
  onRevoked: () => void
}) {
  const [confirm, setConfirm] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function revoke() {
    setBusy(true)
    setError(null)
    const { data, error } = await api.POST('/api/candidate/applications/{application_id}/revoke', {
      params: { path: { application_id: application.id } },
    })
    setBusy(false)
    if (data) {
      onChange(data)
      onRevoked()
    } else setError(errorMessage(error))
  }

  return (
    <li>
      <span className={application.status === 'accepted' ? 'tag' : 'muted'}>
        {applicationStatusWords[application.status]}
      </span>{' '}
      <strong>{application.vacancy_title}</strong> · {application.company_name}
      <span className="muted">
        {' '}
        · {salaryWords(application.salary_from, application.salary_to)} · отклик {dateTimeWords(application.applied_at)}
        {isOpen(application) && ` · ответ до ${dateWords(application.expires_at)}`}
      </span>
      {application.revoked_at ? (
        <p className="hint">
          Доступ отозван {dateTimeWords(application.revoked_at)}: компания видит обезличенную карточку.
        </p>
      ) : confirm ? (
        <div className="actions">
          <span className="hint">
            Компания снова увидит обезличенную карточку — по всем вашим откликам и принятым приглашениям. Вернуть
            доступ — откликом на другую её вакансию или принятым приглашением.
          </span>
          <button type="button" className="button button-small" disabled={busy} onClick={revoke}>
            Отозвать
          </button>
          <button type="button" className="button button-small button-secondary" onClick={() => setConfirm(false)}>
            Оставить
          </button>
        </div>
      ) : (
        <div className="actions">
          <button type="button" className="button button-small button-secondary" onClick={() => setConfirm(true)}>
            Отозвать доступ
          </button>
        </div>
      )}
      {error && <p className="error">{error}</p>}
    </li>
  )
}
