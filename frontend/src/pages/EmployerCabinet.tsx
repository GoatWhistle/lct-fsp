import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { api, errorMessage, type Company, type Need, type SelectionSummary, type SentInvitations } from '../api/client'
import { dateTimeWords, dateWords } from '../candidate/words'
import { Cabinet } from '../components/Cabinet'
import { salaryWords } from '../components/salary'
import { useSentInvitations } from '../employer/invitations'
import { needSalaryWords, workFormatWord } from '../employer/words'
import { invitationStatusWords, isOpen } from '../invitation/words'

/** Кабинет работодателя: профиль компании, потребности и подборки по ним. */
export function EmployerCabinet() {
  const [company, setCompany] = useState<Company | null | undefined>(undefined)
  const [needs, setNeeds] = useState<Need[] | null>(null)
  const [selections, setSelections] = useState<SelectionSummary[]>([])
  const [selectionsError, setSelectionsError] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { sent, error: invitationsError } = useSentInvitations()

  useEffect(() => {
    Promise.all([
      api.GET('/api/employer/company'),
      api.GET('/api/employer/needs'),
      api.GET('/api/employer/selections'),
    ]).then(([company, needs, selections]) => {
      if (company.error || needs.error) {
        setError(errorMessage(company.error ?? needs.error))
        return
      }
      setCompany(company.data ?? null)
      setNeeds(needs.data ?? [])
      // Подборки не загрузились — кабинет с профилем и потребностями всё равно нужен.
      setSelections(selections.data ?? [])
      setSelectionsError(selections.error ? errorMessage(selections.error) : null)
    })
  }, [])

  if (error) return <p className="error">{error}</p>
  if (company === undefined || needs === null) return <p className="muted">Загрузка…</p>

  return (
    <Cabinet title="Кабинет работодателя" upcoming={['Вакансии и отклики кандидатов']}>
      <CompanyCard company={company} />
      <section className="stack">
        <div className="section-head">
          <h2>Потребности</h2>
          <div className="actions">
            <Link to="/employer/needs/text" className="button button-small button-secondary">
              Описать словами
            </Link>
            <Link to="/employer/needs/new" className="button button-small">
              Новая потребность
            </Link>
          </div>
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
      <InvitationList sent={sent} error={invitationsError} />
      <SelectionList selections={selections} error={selectionsError} />
      <div className="card">
        <div className="section-head">
          <h2>Регулярные задания</h2>
          <Link to="/employer/tasks" className="button button-small">
            Задания и ответы
          </Link>
        </div>
        <p>
          Короткие задачи для категории: ответы кандидатов уточняют их профили навыков, открытые
          ответы оцениваете вы.
        </p>
      </div>
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

/** Отправленные приглашения со статусами и остаток бюджета на неделю. */
function InvitationList({ sent, error }: { sent: SentInvitations | null; error: string | null }) {
  if (error) return <p className="error">Приглашения не загрузились: {error}</p>
  if (!sent) return null
  const { budget, invitations } = sent
  return (
    <section className="stack">
      <div className="section-head">
        <h2>Приглашения</h2>
        <span className="muted">
          Осталось на неделю: <strong>{budget.remaining}</strong> из {budget.limit} · обновится{' '}
          {dateTimeWords(budget.resets_at)}
        </span>
      </div>
      {invitations.length === 0 ? (
        <div className="card">
          <p>
            Приглашайте кандидатов из подборки: кандидат увидит компанию, описание и вилку, а вы — его
            имя и контакты, когда он примет приглашение.
          </p>
        </div>
      ) : (
        <div className="card">
          <ul className="selection-list">
            {invitations.map((i) => (
              <li key={i.id}>
                <span className={i.status === 'accepted' ? 'tag' : 'muted'}>{invitationStatusWords[i.status]}</span>{' '}
                <Link to={`/employer/candidates/${i.candidate_id}`}>
                  {i.status === 'accepted' ? 'Контакты кандидата' : 'Карточка кандидата'}
                </Link>
                <span className="muted">
                  {' '}
                  · {salaryWords(i.salary_from, i.salary_to)} · отправлено {dateWords(i.sent_at)}
                  {isOpen(i) && ` · ответ до ${dateWords(i.expires_at)}`}
                </span>
                <p className="hint invitation-summary">{i.description}</p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

/** Последние подборки — в том числе по удалённым потребностям: они открываются по снимку. */
function SelectionList({ selections, error }: { selections: SelectionSummary[]; error: string | null }) {
  if (error) return <p className="error">Подборки не загрузились: {error}</p>
  if (selections.length === 0) return null
  return (
    <section className="stack">
      <h2>Подборки</h2>
      <div className="card">
        <ul className="selection-list">
          {selections.slice(0, 10).map((s) => (
            <li key={s.id}>
              <Link to={`/employer/selections/${s.id}`}>{s.title}</Link>
              <span className="muted">
                {' '}
                · {s.specialization.name} · {s.grade.name} · {dateTimeWords(s.created_at)} · {s.exact_total} в
                категории
                {s.nearby_total > 0 && `, ${s.nearby_total} близких`}
                {s.unconfirmed_total > 0 && `, ${s.unconfirmed_total} с неподтверждённым грейдом`}
                {!s.need_id && ' · потребность удалена'}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </section>
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
        {need.city && ` · ${need.city}`} · {needSalaryWords(need)}
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
            {last.unconfirmed_total > 0 && `, ${last.unconfirmed_total} с неподтверждённым грейдом`}
          </Link>
        )}
      </div>
      {error && <p className="error">{error}</p>}
    </article>
  )
}
