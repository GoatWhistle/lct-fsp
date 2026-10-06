import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api, errorMessage, type Company, type Need } from '../api/client'
import { Cabinet } from '../components/Cabinet'
import { salaryWords, workFormatWord } from '../employer/words'

/** Кабинет работодателя: профиль компании и потребности — вход будущих подборок. */
export function EmployerCabinet() {
  const [company, setCompany] = useState<Company | null | undefined>(undefined)
  const [needs, setNeeds] = useState<Need[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([api.GET('/api/employer/company'), api.GET('/api/employer/needs')]).then(
      ([company, needs]) => {
        if (company.error || needs.error) {
          setError(errorMessage(company.error ?? needs.error))
          return
        }
        setCompany(company.data ?? null)
        setNeeds(needs.data ?? [])
      },
    )
  }, [])

  if (error) return <p className="error">{error}</p>
  if (company === undefined || needs === null) return <p className="muted">Загрузка…</p>

  return (
    <Cabinet
      title="Кабинет работодателя"
      upcoming={['Подборка кандидатов с объяснением', 'Приглашения и их статусы']}
    >
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
          needs.map((need) => <NeedCard key={need.id} need={need} />)
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

function NeedCard({ need }: { need: Need }) {
  const key = need.topics.filter((t) => t.importance === 'key')
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
    </article>
  )
}
