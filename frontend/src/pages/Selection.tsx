import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import {
  api,
  errorMessage,
  type CandidateCard,
  type Invitation,
  type InvitationBudget,
  type Selection as SelectionData,
  type SelectionEntry,
} from '../api/client'
import { dateTimeWords, percent } from '../candidate/words'
import { CandidateCardView } from '../employer/CandidateCardView'
import { InviteAction } from '../employer/Invite'
import { useSentInvitations } from '../employer/invitations'
import { contributionWords, gradeStatusWords, importanceWord, verdictWords, workFormatWord } from '../employer/words'
import { latestByCandidate } from '../invitation/words'

const PAGE = 20

/** Подборка: выдача на момент построения — категория потребности, затем близкие, с объяснением; ниже всех —
 * кандидаты с неподтверждённым грейдом. */
export function Selection() {
  const { id } = useParams()
  const [loaded, setLoaded] = useState<{ id: string; selection: SelectionData | null; error: string | null } | null>(
    null,
  )

  useEffect(() => {
    if (!id) return
    let stale = false
    api
      .GET('/api/employer/selections/{selection_id}', {
        params: { path: { selection_id: id }, query: { limit: PAGE } },
      })
      .then(({ data, error }) => {
        if (!stale) setLoaded({ id, selection: data ?? null, error: data ? null : errorMessage(error) })
      })
    return () => {
      stale = true
    }
  }, [id])

  // Загруженное помечено своим id: «Перестроить» ведёт на новую подборку в том же экземпляре.
  const current = loaded?.id === id ? loaded : null
  if (current?.error) return <p className="error">{current.error}</p>
  if (!current?.selection) return <p className="muted">Загрузка…</p>
  return <SelectionView key={current.selection.id} first={current.selection} />
}

function SelectionView({ first }: { first: SelectionData }) {
  const navigate = useNavigate()
  const [entries, setEntries] = useState<SelectionEntry[]>(first.entries)
  const [loadingMore, setLoadingMore] = useState(false)
  const [rebuilding, setRebuilding] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { sent, error: invitationsError, reload: reloadInvitations } = useSentInvitations()
  const { need } = first
  const total = first.exact_total + first.nearby_total + first.unconfirmed_total
  const invitations: Invitations = useMemo(
    () => ({
      latest: latestByCandidate(sent?.invitations ?? []),
      budget: sent?.budget ?? null,
      onSent: reloadInvitations,
    }),
    [sent, reloadInvitations],
  )

  async function more() {
    setLoadingMore(true)
    const { data, error } = await api.GET('/api/employer/selections/{selection_id}', {
      params: { path: { selection_id: first.id }, query: { offset: entries.length, limit: PAGE } },
    })
    setLoadingMore(false)
    if (data) setEntries((current) => [...current, ...data.entries])
    else setError(errorMessage(error))
  }

  async function rebuild() {
    if (!first.need_id) return
    setRebuilding(true)
    const { data, error } = await api.POST('/api/employer/needs/{need_id}/selections', {
      params: { path: { need_id: first.need_id } },
    })
    setRebuilding(false)
    if (data) navigate(`/employer/selections/${data.id}`)
    else setError(errorMessage(error))
  }

  const exact = entries.filter((e) => e.block === 'exact')
  const nearby = entries.filter((e) => e.block === 'nearby')
  const unconfirmed = entries.filter((e) => e.block === 'unconfirmed')
  const key = need.topics.filter((t) => t.importance === 'key')

  return (
    <section className="stack">
      <div>
        <Link to="/employer">← Кабинет</Link>
      </div>
      <h1>Подборка</h1>
      <div className="card need-card">
        <div className="section-head">
          <div>
            <span className="muted">
              {need.specialization.name} · {need.grade.name} · {workFormatWord(need.work_format)}
              {need.city && ` · ${need.city}`}
            </span>
            <h2 className="company-name">{need.title}</h2>
          </div>
          {first.need_id && (
            <div className="actions">
              <Link to={`/employer/needs/${first.need_id}`} className="button button-small button-secondary">
                Потребность
              </Link>
              <button type="button" className="button button-small" disabled={rebuilding} onClick={rebuild}>
                {rebuilding ? 'Строим…' : 'Перестроить'}
              </button>
            </div>
          )}
        </div>
        {need.stack.length > 0 && (
          <ul className="chips">
            {need.stack.map((t) => (
              <li key={t.code} className="chip">
                {t.name}
              </li>
            ))}
          </ul>
        )}
        {key.length > 0 && <p className="hint">Ключевые темы: {key.map((t) => t.topic.name).join(', ')}</p>}
        <p className="hint">
          Построена {dateTimeWords(first.created_at)} и сохранена: открывается с той же выдачей, даже если
          потребность или профили кандидатов изменились.
          {first.need_id
            ? ' «Перестроить» создаёт новую подборку по текущим данным.'
            : ' Потребность удалена — подборка осталась.'}
        </p>
      </div>

      <div className="card">
        <h2>Как считается соответствие</h2>
        <p>
          Соответствие считается только кандидатам, чью категорию подтвердил тест. По каждой теме — вероятность,
          что уровень кандидата не ниже порога грейда {need.grade.name}; вес темы — её важность в потребности.
          Стек из самоописания ничем не подтверждён и добавляет не больше{' '}
          {Math.round(first.stack_cap * 100)} п. п. Соответствие — сумма вкладов.
        </p>
        <p className="hint">
          Порядок — по соответствию: модель вероятности принятия приглашения ещё не обучена. Кандидаты, которые
          заявили грейд {need.grade.name}, но тест не прошли, — отдельным блоком ниже всех подтверждённых. Карточки
          обезличены — имя и контакты откроются, когда кандидат примет приглашение.
        </p>
        {sent && (
          <p className="hint">
            Осталось приглашений на неделю: {sent.budget.remaining} из {sent.budget.limit}.
          </p>
        )}
        {invitationsError && <p className="error">Приглашения не загрузились: {invitationsError}</p>}
      </div>

      {total === 0 && (
        <div className="card">
          <p>
            Кандидатов с категорией {need.specialization.name} · {need.grade.name} или соседнего грейда пока
            нет. Подборка появится, когда кандидаты пройдут тест.
          </p>
        </div>
      )}

      {first.exact_total > 0 && (
        <Block
          title={`${need.specialization.name} · ${need.grade.name}`}
          count={first.exact_total}
          entries={exact}
          invitations={invitations}
        />
      )}
      {first.nearby_total > 0 && nearby.length > 0 && (
        <Block title="Близкие — соседний грейд" count={first.nearby_total} entries={nearby} invitations={invitations} />
      )}
      {first.unconfirmed_total > 0 && unconfirmed.length > 0 && (
        <Block
          title="Грейд не подтверждён"
          count={first.unconfirmed_total}
          entries={unconfirmed}
          invitations={invitations}
        >
          <p className="hint">
            Заявили грейд {need.grade.name}, но тест его не подтвердил: категории нет, соответствие по темам не
            считается. Порядок — только по стеку потребности в самоописании: по словам кандидата, тестом не
            подтверждено.
          </p>
        </Block>
      )}

      {error && <p className="error">{error}</p>}
      {entries.length < total && (
        <div className="actions">
          <button type="button" className="button button-secondary" disabled={loadingMore} onClick={more}>
            {loadingMore ? 'Загрузка…' : `Показать ещё — осталось ${total - entries.length}`}
          </button>
        </div>
      )}
    </section>
  )
}

/** Приглашения компании для строк выдачи: последнее по кандидату и бюджет недели. */
type Invitations = {
  latest: Map<string, Invitation>
  budget: InvitationBudget | null
  onSent: () => void
}

function Block({
  title,
  count,
  entries,
  invitations,
  children,
}: {
  title: string
  count: number
  entries: SelectionEntry[]
  invitations: Invitations
  children?: ReactNode
}) {
  return (
    <section className="stack">
      <h2>
        {title} <span className="muted">· {count}</span>
      </h2>
      {children}
      {entries.map((entry) =>
        entry.match_score === null ? (
          <UnconfirmedCard key={entry.candidate_id} entry={entry} />
        ) : (
          <EntryCard key={entry.candidate_id} entry={entry} score={entry.match_score} invitations={invitations} />
        ),
      )}
    </section>
  )
}

function stackWords(stack: SelectionEntry['stack']): string {
  if (stack.total === 0) return 'в потребности нет стека'
  if (stack.matched.length === 0) return `нет технологий потребности (0 из ${stack.total})`
  return `${stack.matched.map((t) => t.name).join(', ')} — ${stack.matched.length} из ${stack.total}`
}

/** Кандидат нижнего блока: без скора — только заявленный грейд и стек со слов кандидата. Пригласить
 * можно кандидата с категорией. */
function UnconfirmedCard({ entry }: { entry: SelectionEntry }) {
  return (
    <article className="card match-card">
      <div className="section-head">
        <div>
          <span className="muted">{gradeStatusWords(entry.grade_status)}</span>
          <h3>Кандидат №{entry.rank}</h3>
        </div>
      </div>
      <p>
        Стек: {stackWords(entry.stack)} <span className="hint">— по словам кандидата, тестом не подтверждено</span>
      </p>
      <CardDetails candidateId={entry.candidate_id} />
    </article>
  )
}

function EntryCard({ entry, score, invitations }: { entry: SelectionEntry; score: number; invitations: Invitations }) {
  return (
    <article className="card match-card">
      <div className="section-head">
        <div>
          <span className="muted">
            Категория {entry.grade.name} · {gradeStatusWords(entry.grade_status)}
          </span>
          <h3>Кандидат №{entry.rank}</h3>
        </div>
        <div className="match-score">
          <strong>{Math.round(score * 100)} %</strong>
          <span className="muted">соответствие</span>
        </div>
      </div>
      {entry.stale && <span className="tag">давно не подтверждал уровень</span>}
      <table className="table match-table">
        <caption className="hint">Вклад — в процентных пунктах; сумма вкладов равна соответствию</caption>
        <tbody>
          {entry.topics.map((t) => (
            <tr key={t.topic.code}>
              <th scope="row">
                {t.topic.name}
                <span className="hint importance-source">{importanceWord(t.importance).toLowerCase()}</span>
              </th>
              <td>
                {t.low_data ? (
                  <>
                    данных мало <span className="muted">({percent(t.probability)})</span>
                  </>
                ) : (
                  `${verdictWords[t.verdict]} (${percent(t.probability)})`
                )}
                {t.fsp_confirmed && <span className="tag fsp-tag">подтверждено ФСП</span>}
              </td>
              <td className="num">{contributionWords(t.contribution)}</td>
            </tr>
          ))}
          <tr>
            <th scope="row">
              Стек из самоописания
              <span className="hint importance-source">не подтверждён, не больше потолка</span>
            </th>
            <td>{stackWords(entry.stack)}</td>
            <td className="num">{contributionWords(entry.stack.contribution ?? 0)}</td>
          </tr>
        </tbody>
      </table>
      <InviteAction
        candidateId={entry.candidate_id}
        latest={invitations.latest.get(entry.candidate_id)}
        budget={invitations.budget}
        onSent={invitations.onSent}
      />
      <CardDetails candidateId={entry.candidate_id} />
    </article>
  )
}

/** Карточка кандидата — грузится, когда работодатель её раскрывает. */
function CardDetails({ candidateId }: { candidateId: string }) {
  const [card, setCard] = useState<CandidateCard | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Перечитывается при каждом открытии: после принятия приглашения карточка уже раскрыта.
  function load(open: boolean) {
    if (!open) return
    setError(null)
    api
      .GET('/api/employer/candidates/{candidate_id}', { params: { path: { candidate_id: candidateId } } })
      .then(({ data, error }) => {
        if (data) setCard(data)
        else setError(errorMessage(error))
      })
  }

  return (
    <details onToggle={(e) => load(e.currentTarget.open)}>
      <summary>Карточка кандидата</summary>
      {error && <p className="error">{error}</p>}
      {!card && !error && <p className="muted">Загрузка…</p>}
      {card && (
        <>
          <CandidateCardView card={card} />
          <Link to={`/employer/candidates/${candidateId}`}>Открыть карточку отдельно</Link>
        </>
      )}
    </details>
  )
}
