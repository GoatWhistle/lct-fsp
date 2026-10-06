import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import {
  api,
  errorMessage,
  type Need,
  type NeedInput,
  type Technology,
  type TopicImportance,
  type TopicImportanceRow,
  type WorkFormat,
} from '../api/client'
import { useEmployerCatalog, type EmployerCatalog } from '../employer/catalog'
import { importances, workFormats } from '../employer/words'

type Draft = {
  title: string
  team_description: string
  specialization: string
  grade: string
  stack: string[]
  work_format: WorkFormat
  city: string
  salary_from: string
  salary_to: string
  topic_importance: Record<string, TopicImportance>
}

function emptyDraft(catalog: EmployerCatalog): Draft {
  return {
    title: '',
    team_description: '',
    specialization: catalog.specializations[0]?.code ?? '',
    grade: catalog.grades.find((g) => g.code === 'middle')?.code ?? catalog.grades[0]?.code ?? '',
    stack: [],
    work_format: 'hybrid',
    city: '',
    salary_from: '',
    salary_to: '',
    topic_importance: {},
  }
}

function draftOf(need: Need): Draft {
  return {
    title: need.title,
    team_description: need.team_description,
    specialization: need.specialization.code,
    grade: need.grade.code,
    stack: need.stack.map((t) => t.code),
    work_format: need.work_format,
    city: need.city ?? '',
    salary_from: need.salary_from?.toString() ?? '',
    salary_to: need.salary_to?.toString() ?? '',
    topic_importance: Object.fromEntries(
      need.topics.filter((t) => t.edited).map((t) => [t.topic.code, t.importance]),
    ),
  }
}

/** Технологии, связанные с темами специализации, и остальные справочника. */
function splitTechnologies(catalog: EmployerCatalog, specialization: string) {
  const chosen = catalog.specializations.find((s) => s.code === specialization)
  const own = new Set(chosen?.topics.map((t) => t.code))
  const related = catalog.technologies.filter((t) => t.topics.some((topic) => own.has(topic)))
  return { chosen, related, others: catalog.technologies.filter((t) => !related.includes(t)) }
}

function inputOf(draft: Draft): NeedInput {
  const salary = (value: string) => (value.trim() === '' ? null : Number(value))
  return {
    ...draft,
    city: draft.city.trim() || null,
    salary_from: salary(draft.salary_from),
    salary_to: salary(draft.salary_to),
  }
}

/** Потребность: кого ищете, стек, грейд, формат, вилка. Важность тем выводится из стека, её можно поправить. */
export function NeedForm() {
  const { id } = useParams()
  const { catalog, failed } = useEmployerCatalog()
  // Загруженное помечено своим id: маршруты «новая» и «правка» делят один экземпляр компонента.
  const [loaded, setLoaded] = useState<{ id: string; need: Need | null; error: string | null } | null>(null)

  useEffect(() => {
    if (!id) return
    api.GET('/api/employer/needs/{need_id}', { params: { path: { need_id: id } } }).then(({ data, error }) => {
      setLoaded({ id, need: data ?? null, error: data ? null : errorMessage(error) })
    })
  }, [id])

  const current = id && loaded?.id === id ? loaded : null
  if (failed) return <p className="error">Не удалось загрузить справочники</p>
  if (current?.error) return <p className="error">{current.error}</p>
  if (!catalog || (id && !current?.need)) return <p className="muted">Загрузка…</p>
  const need = current?.need ?? null
  return <NeedEditor key={need?.id ?? 'new'} catalog={catalog} need={need} />
}

function NeedEditor({ catalog, need }: { catalog: EmployerCatalog; need: Need | null }) {
  const id = need?.id
  const navigate = useNavigate()
  const [draft, setDraft] = useState<Draft>(() => (need ? draftOf(need) : emptyDraft(catalog)))
  const [topics, setTopics] = useState<TopicImportanceRow[]>(need?.topics ?? [])
  const [topicsError, setTopicsError] = useState<string | null>(null)
  const [othersOpen, setOthersOpen] = useState(() =>
    splitTechnologies(catalog, draft.specialization).others.some((t) => draft.stack.includes(t.code)),
  )
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  // Важность тем считает бэкенд той же функцией, что у сохранённой потребности.
  const { specialization, stack, topic_importance: edited } = draft
  useEffect(() => {
    let stale = false
    api
      .POST('/api/employer/needs/topic-importance', {
        body: { specialization, stack, topic_importance: edited },
      })
      .then(({ data, error }) => {
        if (stale) return
        setTopics(data ?? [])
        setTopicsError(data ? null : errorMessage(error))
      })
    return () => {
      stale = true
    }
  }, [specialization, stack, edited])

  function change(changes: Partial<Draft>) {
    setDraft((current) => ({ ...current, ...changes }))
  }

  // Темы прошлой специализации убираем сразу: их правки новая специализация не примет.
  function chooseSpecialization(code: string) {
    setTopics([])
    change({ specialization: code, topic_importance: {} })
  }

  function toggleTechnology(code: string) {
    const stack = draft.stack.includes(code) ? draft.stack.filter((c) => c !== code) : [...draft.stack, code]
    change({ stack })
  }

  function setImportance(topic: string, importance: TopicImportance | null) {
    const { [topic]: _, ...rest } = draft.topic_importance
    change({ topic_importance: importance ? { ...rest, [topic]: importance } : rest })
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    const body = inputOf(draft)
    const { data, error } = id
      ? await api.PUT('/api/employer/needs/{need_id}', { params: { path: { need_id: id } }, body })
      : await api.POST('/api/employer/needs', { body })
    setSubmitting(false)
    if (data) navigate('/employer')
    else setError(errorMessage(error))
  }

  async function remove() {
    if (!id || !window.confirm('Удалить потребность?')) return
    setSubmitting(true)
    const { error, response } = await api.DELETE('/api/employer/needs/{need_id}', {
      params: { path: { need_id: id } },
    })
    setSubmitting(false)
    if (response.ok) navigate('/employer')
    else setError(errorMessage(error))
  }

  const { chosen, related, others } = splitTechnologies(catalog, draft.specialization)

  return (
    <section className="stack">
      <h1>{id ? 'Потребность' : 'Новая потребность'}</h1>
      <form onSubmit={submit} className="card form">
        <label className="field">
          Кого ищете
          <input
            required
            maxLength={200}
            placeholder="Бэкенд-разработчик в команду платежей"
            value={draft.title}
            onChange={(e) => change({ title: e.target.value })}
          />
        </label>
        <label className="field">
          Чем занимается команда
          <textarea
            rows={3}
            maxLength={2000}
            value={draft.team_description}
            onChange={(e) => change({ team_description: e.target.value })}
          />
        </label>

        <fieldset className="choice-grid">
          <legend>Специализация</legend>
          {catalog.specializations.map((s) => (
            <label key={s.code} className={draft.specialization === s.code ? 'role-option selected' : 'role-option'}>
              <input
                type="radio"
                name="specialization"
                value={s.code}
                checked={draft.specialization === s.code}
                onChange={() => chooseSpecialization(s.code)}
              />
              <strong>{s.name}</strong>
              <span className="muted">{s.has_test ? `${s.topics.length} тем` : 'тест готовится'}</span>
            </label>
          ))}
        </fieldset>
        {chosen && !chosen.has_test && (
          <p className="hint">
            Тест по этой специализации ещё готовится: кандидатов с такой категорией пока нет, подборка
            будет пустой.
          </p>
        )}

        <fieldset className="choice-grid">
          <legend>Грейд</legend>
          {catalog.grades.map((g) => (
            <label key={g.code} className={draft.grade === g.code ? 'role-option selected' : 'role-option'}>
              <input
                type="radio"
                name="grade"
                value={g.code}
                checked={draft.grade === g.code}
                onChange={() => change({ grade: g.code })}
              />
              <strong>{g.name}</strong>
            </label>
          ))}
        </fieldset>

        <fieldset className="plain">
          <legend>Стек</legend>
          <TechnologyChips technologies={related} selected={draft.stack} onToggle={toggleTechnology} />
          <details open={othersOpen} onToggle={(e) => setOthersOpen(e.currentTarget.open)}>
            <summary>Другие технологии</summary>
            <p className="hint">На важность тем специализации не влияют, но учитываются в подборке.</p>
            <TechnologyChips technologies={others} selected={draft.stack} onToggle={toggleTechnology} />
          </details>
        </fieldset>

        {topicsError ? (
          <p className="error">Важность тем не посчиталась: {topicsError}</p>
        ) : (
          <TopicImportanceTable topics={topics} onChange={setImportance} />
        )}

        <fieldset className="choice-grid">
          <legend>Формат работы</legend>
          {workFormats.map((f) => (
            <label key={f.value} className={draft.work_format === f.value ? 'role-option selected' : 'role-option'}>
              <input
                type="radio"
                name="work_format"
                value={f.value}
                checked={draft.work_format === f.value}
                onChange={() => change({ work_format: f.value })}
              />
              <strong>{f.title}</strong>
            </label>
          ))}
        </fieldset>
        <label className="field">
          Город
          <input
            required={draft.work_format !== 'remote'}
            maxLength={100}
            value={draft.city}
            onChange={(e) => change({ city: e.target.value })}
          />
          <span className="hint">
            {draft.work_format === 'remote' ? 'Для удалённой работы — по желанию' : 'Где офис'}
          </span>
        </label>

        <fieldset className="plain">
          <legend>Вилка, ₽ в месяц</legend>
          <div className="field-row">
            <label className="field">
              От
              <input
                type="number"
                min={1}
                inputMode="numeric"
                required={draft.salary_to !== ''}
                value={draft.salary_from}
                onChange={(e) => change({ salary_from: e.target.value })}
              />
            </label>
            <label className="field">
              До
              <input
                type="number"
                min={draft.salary_from || 1}
                inputMode="numeric"
                required={draft.salary_from !== ''}
                value={draft.salary_to}
                onChange={(e) => change({ salary_to: e.target.value })}
              />
            </label>
          </div>
          <span className="hint">
            Можно не указывать. В приглашении кандидату вилка обязательна — он видит условия до начала
            общения.
          </span>
        </fieldset>

        {error && <p className="error">{error}</p>}
        <div className="actions">
          <button type="submit" className="button" disabled={submitting}>
            {id ? 'Сохранить' : 'Создать потребность'}
          </button>
          <Link to="/employer">Отмена</Link>
          {id && (
            <button type="button" className="link-button danger" disabled={submitting} onClick={remove}>
              Удалить
            </button>
          )}
        </div>
      </form>
    </section>
  )
}

function TechnologyChips({
  technologies,
  selected,
  onToggle,
}: {
  technologies: Technology[]
  selected: string[]
  onToggle: (code: string) => void
}) {
  return (
    <div className="chips">
      {technologies.map((t) => (
        <button
          key={t.code}
          type="button"
          className={selected.includes(t.code) ? 'chip chip-toggle selected' : 'chip chip-toggle'}
          aria-pressed={selected.includes(t.code)}
          onClick={() => onToggle(t.code)}
        >
          {t.name}
        </button>
      ))}
    </div>
  )
}

/** Важность тем: по умолчанию из стека, работодатель правит. Задаёт вес темы в подборке. */
function TopicImportanceTable({
  topics,
  onChange,
}: {
  topics: TopicImportanceRow[]
  onChange: (topic: string, importance: TopicImportance | null) => void
}) {
  if (topics.length === 0) return null
  return (
    <fieldset className="plain">
      <legend>Важность тем</legend>
      <p className="hint">
        По умолчанию выводится из стека: чем больше технологий стека связано с темой, тем она
        важнее. Важность задаёт вес темы в подборке — поправьте, если стек говорит не всё.
      </p>
      <table className="table importance-table">
        <tbody>
          {topics.map((row) => (
            <tr key={row.topic.code}>
              <th scope="row">
                {row.topic.name}
                <span className="hint importance-source">
                  {row.edited ? (
                    <>
                      ваша правка ·{' '}
                      <button type="button" className="link-button" onClick={() => onChange(row.topic.code, null)}>
                        вернуть из стека
                      </button>
                    </>
                  ) : row.technologies.length > 0 ? (
                    `из стека: ${row.technologies.map((t) => t.name).join(', ')}`
                  ) : (
                    'в стеке нет связанных технологий'
                  )}
                </span>
              </th>
              <td>
                <div className="segmented" role="group" aria-label={`Важность: ${row.topic.name}`}>
                  {importances.map((i) => (
                    <button
                      key={i.value}
                      type="button"
                      className={row.importance === i.value ? 'selected' : ''}
                      aria-pressed={row.importance === i.value}
                      onClick={() => onChange(row.topic.code, i.value)}
                    >
                      {i.title}
                    </button>
                  ))}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </fieldset>
  )
}
