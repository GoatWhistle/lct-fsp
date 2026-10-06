import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { api, errorMessage, type Company, type Need, type SelectionSummary } from '../api/client'
import { dateWords } from '../candidate/words'
import { Cabinet } from '../components/Cabinet'
import { salaryWords, workFormatWord } from '../employer/words'

/** Кабинет работодателя: профиль компании, потребности и подборки по ним. */
export function EmployerCabinet() {
  const [company, setCompany] = useState<Company | null | undefined>(undefined)
  const [needs, setNeeds] = useState<Need[] | null>(null)
  const [selections, setSelections] = useState<SelectionSummary[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      api.GET('/api/employer/company'),
      api.GET('/api/employer/needs'),
      api.GET('/api/employer/selections'),
    ]).then(([company, needs, selections]) => {
      if (company.error || needs.error || selections.error) {
        setError(errorMessage(company.error ?? needs.error ?? selections.error))
        return
      }
      setCompany(company.data ?? null)
      setNeeds(needs.data ?? [])
      setSelections(selections.data ?? [])
    })
  }, [])

  if (error) return <p className="error">{error}</p>
  if (company === undefined || needs === null) return <p className="muted">Загрузка…</p>

  return (
    <Cabinet title="Кабинет работодателя" upcoming={['Приглашения и их статусы']}>
      <CompanyCard company={company} />
      <section className="stack">
        <div className="section-head">
          <h2>Потребности</h2>
          <Link to="/employer/needs/new" className="button button-small">
            Новая потребность
          </Link>
        </div>
        {needs.length === 0 ? (
          <div className="card">
            <p>
              Опишите, кого ищете: специализацию, грейд, стек и формат работы. По потребности
              строится подборка кандидатов, чья категория подтверждена тестом.
            </p>
          </div>
        ) : (
          needs.map((need) => (
            <NeedCard key={need.id} need={need} selections={selections.filter((s) => s.need_id === need.id)} />
          ))
        )}
      </section>
    </Cabinet>
  )
}

function CompanyCard({ company }: { company: Company | null }) {
  if (!company) {
    return (
      <div className="card form">
        <h2>Профиль компании</h2>
        <p>
          Расскажите о компании: кандидат увидит её название, описание и контакты в приглашении.
          Потребности можно заводить и без профиля.
        </p>
        <div className="actions">
          <Link to="/employer/company" className="button">
            Заполнить профиль
          </Link>
        </div>
      </div>
    )
  }
  return (
    <div className="card">
      <div className="section-head">
        <div>
          <span className="muted">{company.industry.name}</span>
          <h2 className="company-name">{company.name}</h2>
        </div>
        <Link to="/employer/company" className="button button-small button-secondary">
          Изменить
        </Link>
      </div>
      <p className="prewrap">{company.description}</p>
      <p className="muted">
        {[company.contact_email, company.contact_phone].filter(Boolean).join(' · ')}
        {company.website && (
          <>
            {' · '}
            <a href={company.website} target="_blank" rel="noreferrer">
              {company.website.replace(/^https?:\/\//, '').replace(/\/$/, '')}
            </a>
          </>
        )}
      </p>
    </div>
  )
}

function NeedCard({ need, selections }: { need: Need; selections: SelectionSummary[] }) {
  const navigate = useNavigate()
  const [building, setBuilding] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const key = need.topics.filter((t) => t.importance === 'key')
  // Список подборок — новые сверху.
  const last = selections[0]

  async function build() {
    setBuilding(true)
    setError(null)
    const { data, error } = await api.POST('/api/employer/needs/{need_id}/selections', {
      params: { path: { need_id: need.id } },
    })
    setBuilding(false)
    if (data) navigate(`/employer/selections/${data.id}`)
    else setError(errorMessage(error))
  }

  return (
    <article className="card need-card">
      <div className="section-head">
        <div>
          <span className="muted">
            {need.specialization.name} · {need.grade.name}
          </span>
          <h3>{need.title}</h3>
        </div>
        <Link to={`/employer/needs/${need.id}`} className="button button-small button-secondary">
          Изменить
        </Link>
      </div>
      <p className="muted">
        {workFormatWord(need.work_format)}
        {need.city && ` · ${need.city}`} · {salaryWords(need)}
      </p>
      {need.stack.length > 0 && (
        <ul className="chips">
          {need.stack.map((t) => (
            <li key={t.code} className="chip">
              {t.name}
            </li>
          ))}
        </ul>
      )}
      {key.length > 0 && (
        <p className="hint">Ключевые темы: {key.map((t) => t.topic.name).join(', ')}</p>
      )}
      <div className="actions">
        <button type="button" className="button button-small" disabled={building} onClick={build}>
          {building ? 'Строим подборку…' : 'Сформировать подборку'}
        </button>
        {last && (
          <Link to={`/employer/selections/${last.id}`}>
            Последняя подборка от {dateWords(last.created_at)}: {last.exact_total} в категории
            {last.nearby_total > 0 && `, ${last.nearby_total} близких`}
          </Link>
        )}
      </div>
      {error && <p className="error">{error}</p>}
    </article>
  )
}
