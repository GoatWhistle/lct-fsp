import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { api, errorCode, errorMessage, type Application, type Vacancy, type VacancyInput, type WorkFormat } from '../api/client'
import { useCatalog } from '../candidate/catalog'
import { dateTimeWords, dateWords } from '../candidate/words'
import { SalaryRangeInput } from '../components/SalaryInput'
import { applicationStatusWords, isOpen, vacancyTermsWords } from '../vacancy/words'
import { workFormats } from './words'

/**
 * Вакансии компании и отклики на них. Отклик сразу открывает компании имя, контакты и профиль
 * кандидата — без ожидаемой зарплаты; бюджет приглашений отклики не тратят. Снятая с публикации
 * вакансия уходит из общего списка, поданные отклики остаются.
 */
export function Vacancies({ hasCompany }: { hasCompany: boolean }) {
  const [vacancies, setVacancies] = useState<Vacancy[] | null>(null)
  const [applications, setApplications] = useState<Application[]>([])
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  const load = useCallback(() => {
    Promise.all([api.GET('/api/employer/vacancies'), api.GET('/api/employer/applications')]).then(
      ([vacancies, applications]) => {
        if (vacancies.data && applications.data) {
          setVacancies(vacancies.data)
          setApplications(applications.data)
          setError(null)
        } else setError(errorMessage(vacancies.error ?? applications.error))
      },
    )
  }, [])

  useEffect(load, [load])

  function replaceApplication(next: Application) {
    setApplications((current) => current.map((a) => (a.id === next.id ? next : a)))
  }

  if (error) return <p className="error">Вакансии не загрузились: {error}</p>
  if (!vacancies) return null
  const byVacancy = new Map<string, Application[]>()
  for (const a of applications) byVacancy.set(a.vacancy_id, [...(byVacancy.get(a.vacancy_id) ?? []), a])
  return (
    <section className="stack">
      <div className="section-head">
        <h2>Вакансии</h2>
        {hasCompany && !creating && (
          <button type="button" className="button button-small" onClick={() => setCreating(true)}>
            Новая вакансия
          </button>
        )}
      </div>
      {!hasCompany && (
        <div className="card">
          <p>Вакансии публикует компания: сначала заполните её профиль — кандидат увидит, чья вакансия.</p>
        </div>
      )}
      {creating && (
        <VacancyForm
          onCancel={() => setCreating(false)}
          onSaved={() => {
            setCreating(false)
            load()
          }}
        />
      )}
      {hasCompany && vacancies.length === 0 && !creating && (
        <div className="card">
          <p>
            Опубликуйте вакансию с вилкой — кандидаты откликнутся сами. Отклик сразу открывает вам имя и
            контакты кандидата и не тратит бюджет приглашений.
          </p>
        </div>
      )}
      {vacancies.map((v) => (
        <VacancyCard
          key={v.id}
          vacancy={v}
          applications={byVacancy.get(v.id) ?? []}
          onChange={load}
          onApplication={replaceApplication}
        />
      ))}
    </section>
  )
}

function VacancyCard({
  vacancy,
  applications,
  onChange,
  onApplication,
}: {
  vacancy: Vacancy
  applications: Application[]
  onChange: () => void
  onApplication: (application: Application) => void
}) {
  const [editing, setEditing] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function archive() {
    setBusy(true)
    setError(null)
    const { data, error } = await api.POST('/api/employer/vacancies/{vacancy_id}/archive', {
      params: { path: { vacancy_id: vacancy.id } },
    })
    setBusy(false)
    if (data) onChange()
    else setError(errorMessage(error))
  }

  if (editing) {
    return (
      <VacancyForm
        vacancy={vacancy}
        onCancel={() => setEditing(false)}
        onSaved={() => {
          setEditing(false)
          onChange()
        }}
      />
    )
  }
  return (
    <article className="card need-card">
      <div className="section-head">
        <div>
          <span className="muted">
            {vacancy.archived_at ? `Снята с публикации ${dateWords(vacancy.archived_at)}` : `Опубликована ${dateWords(vacancy.published_at)}`}
          </span>
          <h3>{vacancy.title}</h3>
        </div>
        {!vacancy.archived_at && (
          <div className="actions">
            <button type="button" className="button button-small button-secondary" onClick={() => setEditing(true)}>
              Изменить
            </button>
            <button type="button" className="button button-small button-secondary" disabled={busy} onClick={archive}>
              Снять с публикации
            </button>
          </div>
        )}
      </div>
      <p className="muted">{vacancyTermsWords(vacancy)}</p>
      {vacancy.description && <p className="prewrap">{vacancy.description}</p>}
      {error && <p className="error">{error}</p>}
      <h3>Отклики{applications.length > 0 && `: ${applications.length}`}</h3>
      {applications.length === 0 ? (
        <p className="hint">Откликов пока нет.</p>
      ) : (
        <ul className="selection-list">
          {applications.map((a) => (
            <IncomingApplication key={a.id} application={a} onChange={onApplication} onStale={onChange} />
          ))}
        </ul>
      )}
    </article>
  )
}

const STALE = new Set(['application_transition_not_allowed'])

/** Отклик: открыть карточку кандидата — отклик просмотрен; принять или отклонить. */
function IncomingApplication({
  application,
  onChange,
  onStale,
}: {
  application: Application
  onChange: (application: Application) => void
  /** Статус на экране устарел — истёк срок или решение уже записано: перечитать отклики. */
  onStale: () => void
}) {
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const params = { params: { path: { application_id: application.id } } }

  async function run(request: () => Promise<{ data?: Application; error?: unknown }>): Promise<boolean> {
    setBusy(true)
    setError(null)
    const { data, error } = await request()
    setBusy(false)
    if (data) {
      onChange(data)
      return true
    }
    setError(errorMessage(error))
    if (STALE.has(errorCode(error) ?? '')) onStale()
    return false
  }

  async function openCard() {
    if (await run(() => api.POST('/api/employer/applications/{application_id}/view', params))) {
      navigate(`/employer/candidates/${application.candidate_id}`)
    }
  }

  return (
    <li>
      <span className={application.status === 'sent' ? 'tag' : 'muted'}>
        {application.status === 'sent' ? 'новый' : applicationStatusWords[application.status]}
      </span>{' '}
      {/* После отзыва карточка кандидата без теста по отклику больше не открывается. */}
      {application.revoked_at ? (
        <span className="fsp-tag">доступ отозван</span>
      ) : (
        <button type="button" className="link-button" disabled={busy} onClick={openCard}>
          Контакты и профиль кандидата
        </button>
      )}
      <span className="muted">
        {' '}
        · отклик {dateTimeWords(application.applied_at)}
        {isOpen(application) && ` · ответить до ${dateWords(application.expires_at)}`}
      </span>
      {isOpen(application) && (
        <div className="actions">
          <button
            type="button"
            className="button button-small"
            disabled={busy}
            onClick={() => run(() => api.POST('/api/employer/applications/{application_id}/accept', params))}
          >
            Принять
          </button>
          <button
            type="button"
            className="button button-small button-secondary"
            disabled={busy}
            onClick={() => run(() => api.POST('/api/employer/applications/{application_id}/decline', params))}
          >
            Отклонить
          </button>
        </div>
      )}
      {application.revoked_at && (
        <p className="hint">Кандидат отозвал доступ {dateWords(application.revoked_at)}: вы снова видите обезличенную карточку.</p>
      )}
      {error && <p className="error">{error}</p>}
    </li>
  )
}

type Draft = {
  title: string
  description: string
  specialization: string
  grade: string
  work_formats: WorkFormat[]
  salary_from: string
  salary_to: string
}

function draftOf(vacancy?: Vacancy): Draft {
  if (!vacancy) {
    return { title: '', description: '', specialization: '', grade: '', work_formats: [], salary_from: '', salary_to: '' }
  }
  return {
    title: vacancy.title,
    description: vacancy.description,
    specialization: vacancy.specialization.code,
    grade: vacancy.grade.code,
    work_formats: vacancy.work_formats,
    salary_from: String(vacancy.salary_from),
    salary_to: String(vacancy.salary_to),
  }
}

/** Публикация и правка вакансии: вилка обязательна, суммы — до вычета НДФЛ. */
function VacancyForm({ vacancy, onCancel, onSaved }: { vacancy?: Vacancy; onCancel: () => void; onSaved: () => void }) {
  const { catalog, failed } = useCatalog()
  const [draft, setDraft] = useState<Draft>(() => draftOf(vacancy))
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function change(patch: Partial<Draft>) {
    setDraft((current) => ({ ...current, ...patch }))
  }

  function toggleFormat(format: WorkFormat) {
    change({
      work_formats: draft.work_formats.includes(format)
        ? draft.work_formats.filter((f) => f !== format)
        : [...draft.work_formats, format],
    })
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (draft.work_formats.length === 0) {
      setError('Отметьте хотя бы один формат работы')
      return
    }
    const body: VacancyInput = {
      title: draft.title,
      description: draft.description,
      specialization: draft.specialization,
      grade: draft.grade,
      work_formats: draft.work_formats,
      salary_from: Number(draft.salary_from),
      salary_to: Number(draft.salary_to),
    }
    setSubmitting(true)
    setError(null)
    const { error } = vacancy
      ? await api.PUT('/api/employer/vacancies/{vacancy_id}', { params: { path: { vacancy_id: vacancy.id } }, body })
      : await api.POST('/api/employer/vacancies', { body })
    setSubmitting(false)
    if (error) setError(errorMessage(error))
    else onSaved()
  }

  if (failed) return <p className="error">Не удалось загрузить справочники</p>
  if (!catalog) return <p className="muted">Загрузка…</p>
  return (
    <form className="card form" onSubmit={submit}>
      <h2>{vacancy ? 'Правка вакансии' : 'Новая вакансия'}</h2>
      <label className="field">
        Должность
        <input required maxLength={200} value={draft.title} onChange={(e) => change({ title: e.target.value })} />
      </label>
      <label className="field">
        Описание
        <textarea
          rows={5}
          maxLength={5000}
          value={draft.description}
          onChange={(e) => change({ description: e.target.value })}
        />
        <span className="hint">Задачи, команда, условия</span>
      </label>
      <div className="field-row">
        <label className="field">
          Специализация
          <select required value={draft.specialization} onChange={(e) => change({ specialization: e.target.value })}>
            <option value="" disabled>
              Выберите специализацию
            </option>
            {catalog.specializations.map((s) => (
              <option key={s.code} value={s.code}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Грейд
          <select required value={draft.grade} onChange={(e) => change({ grade: e.target.value })}>
            <option value="" disabled>
              Выберите грейд
            </option>
            {catalog.grades.map((g) => (
              <option key={g.code} value={g.code}>
                {g.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      <fieldset className="plain">
        <legend>Формат работы</legend>
        <div className="chips">
          {workFormats.map((f) => (
            <button
              key={f.value}
              type="button"
              className={draft.work_formats.includes(f.value) ? 'chip chip-toggle selected' : 'chip chip-toggle'}
              aria-pressed={draft.work_formats.includes(f.value)}
              onClick={() => toggleFormat(f.value)}
            >
              {f.title}
            </button>
          ))}
        </div>
        <span className="hint">Отметьте все подходящие</span>
      </fieldset>
      <SalaryRangeInput
        range={{ from: draft.salary_from, to: draft.salary_to }}
        onChange={({ from, to }) => change({ salary_from: from, salary_to: to })}
        hint="Обязательна: кандидат видит условия до отклика."
      />
      {error && <p className="error">{error}</p>}
      <div className="actions">
        <button type="submit" className="button" disabled={submitting}>
          {vacancy ? 'Сохранить' : 'Опубликовать'}
        </button>
        <button type="button" className="button button-secondary" onClick={onCancel}>
          Отмена
        </button>
      </div>
    </form>
  )
}
