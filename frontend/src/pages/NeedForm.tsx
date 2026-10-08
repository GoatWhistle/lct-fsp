import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import {
  api,
  errorMessage,
  type DraftField,
  type Need,
  type NeedInput,
  type Technology,
  type TopicImportance,
  type TopicImportanceRow,
  type WorkFormat,
} from '../api/client'
import { SalaryRangeInput } from '../components/SalaryInput'
import { useEmployerCatalog, type EmployerCatalog } from '../employer/catalog'
import { importances, workFormats } from '../employer/words'

export type Draft = {
  title: string
  team_description: string
  specialization: string
  grade: string
  stack: string[]
  // Пусто — формат не выбран: черновик из текста его не нашёл.
  work_format: WorkFormat | ''
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

/** Поля черновика из текста, которые экран выделяет: неуверенные и не найденные в тексте. */
export type DraftMarks = { uncertain: DraftField[]; missing: DraftField[] }

function inputOf(draft: Draft): NeedInput {
  const salary = (value: string) => (value.trim() === '' ? null : Number(value))
  return {
    ...draft,
    // Пустой формат не пройдёт обязательный выбор в форме — сюда он не доходит.
    work_format: draft.work_format as WorkFormat,
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

type EditorProps = {
  catalog: EmployerCatalog
  need: Need | null
  // Черновик из текста: форма открывается с ним и умеет строить подборку без сохранения.
  initial?: Draft
  marks?: DraftMarks
}

export function NeedEditor({ catalog, need, initial, marks }: EditorProps) {
  const id = need?.id
  const fromText = initial !== undefined
  const navigate = useNavigate()
  const [draft, setDraft] = useState<Draft>(() => initial ?? (need ? draftOf(need) : emptyDraft(catalog)))
  // Выделение снимается с поля, как только работодатель его поправил.
  const [flagged, setFlagged] = useState<DraftMarks>(() => marks ?? { uncertain: [], missing: [] })
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
    if (!specialization) return
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

  function change(changes: Partial<Draft>, field?: DraftField) {
    setDraft((current) => ({ ...current, ...changes }))
    if (field) {
      setFlagged((current) => ({
        uncertain: current.uncertain.filter((f) => f !== field),
        missing: current.missing.filter((f) => f !== field),
      }))
    }
  }

  function mark(field: DraftField): ReactNode {
    if (flagged.uncertain.includes(field)) return <span className="draft-mark">Проверьте: система не уверена</span>
    if (flagged.missing.includes(field)) return <span className="draft-mark">В тексте не нашлось — укажите</span>
    return null
  }

  function flagClass(field: DraftField, base: string): string {
    return flagged.uncertain.includes(field) || flagged.missing.includes(field) ? `${base} flagged` : base
  }

  // Темы прошлой специализации убираем сразу: их правки новая специализация не примет.
  function chooseSpecialization(code: string) {
    setTopics([])
    change({ specialization: code, topic_importance: {} }, 'specialization')
  }

  function toggleTechnology(code: string) {
    const stack = draft.stack.includes(code) ? draft.stack.filter((c) => c !== code) : [...draft.stack, code]
    change({ stack }, 'stack')
  }

  function setImportance(topic: string, importance: TopicImportance | null) {
    const { [topic]: _, ...rest } = draft.topic_importance
    change({ topic_importance: importance ? { ...rest, [topic]: importance } : rest })
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    const body = inputOf(draft)
    const pressed = (event.nativeEvent as SubmitEvent).submitter
    if (pressed instanceof HTMLButtonElement && pressed.value === 'selection') {
      // Подборка по черновику без сохранения; черновик едет с ней — вернуться и поправить.
      const { data, error } = await api.POST('/api/employer/selections', { body })
      setSubmitting(false)
      if (data) navigate(`/employer/selections/${data.id}`, { state: { draft, marks: flagged } })
      else setError(errorMessage(error))
      return
    }
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
      {!fromText && <h1>{id ? 'Потребность' : 'Новая потребность'}</h1>}
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

        <fieldset className={flagClass('specialization', 'choice-grid')}>
          <legend>Специализация {mark('specialization')}</legend>
          {catalog.specializations.map((s) => (
            <label key={s.code} className={draft.specialization === s.code ? 'role-option selected' : 'role-option'}>
              <input
                type="radio"
                name="specialization"
                required
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

        <fieldset className={flagClass('grade', 'choice-grid')}>
          <legend>Грейд {mark('grade')}</legend>
          {catalog.grades.map((g) => (
            <label key={g.code} className={draft.grade === g.code ? 'role-option selected' : 'role-option'}>
              <input
                type="radio"
                name="grade"
                required
                value={g.code}
                checked={draft.grade === g.code}
                onChange={() => change({ grade: g.code }, 'grade')}
              />
              <strong>{g.name}</strong>
            </label>
          ))}
        </fieldset>

        <fieldset className={flagClass('stack', 'plain')}>
          <legend>Стек {mark('stack')}</legend>
          <TechnologyChips technologies={related} selected={draft.stack} onToggle={toggleTechnology} />
          <details open={othersOpen} onToggle={(e) => setOthersOpen(e.currentTarget.open)}>
            <summary>Другие технологии</summary>
            <p className="hint">На важность тем специализации не влияют, но учитываются в подборке.</p>
            <TechnologyChips technologies={others} selected={draft.stack} onToggle={toggleTechnology} />
          </details>
        </fieldset>

        {!draft.specialization ? null : topicsError ? (
          <p className="error">Важность тем не посчиталась: {topicsError}</p>
        ) : (
          <TopicImportanceTable topics={topics} onChange={setImportance} />
        )}

        <fieldset className={flagClass('work_format', 'choice-grid')}>
          <legend>Формат работы {mark('work_format')}</legend>
          {workFormats.map((f) => (
            <label key={f.value} className={draft.work_format === f.value ? 'role-option selected' : 'role-option'}>
              <input
                type="radio"
                name="work_format"
                required
                value={f.value}
                checked={draft.work_format === f.value}
                onChange={() => change({ work_format: f.value }, 'work_format')}
              />
              <strong>{f.title}</strong>
            </label>
          ))}
        </fieldset>
        <label className={flagClass('city', 'field')}>
          <span>Город {mark('city')}</span>
          <input
            required={draft.work_format !== 'remote'}
            maxLength={100}
            value={draft.city}
            onChange={(e) => change({ city: e.target.value }, 'city')}
          />
          <span className="hint">
            {draft.work_format === 'remote' ? 'Для удалённой работы — по желанию' : 'Где офис'}
          </span>
        </label>

        <div className={flagClass('salary', 'plain')}>
          {mark('salary')}
          <SalaryRangeInput
            range={{ from: draft.salary_from, to: draft.salary_to }}
            onChange={({ from, to }) => change({ salary_from: from, salary_to: to }, 'salary')}
            optional
            hint={
              fromText
                ? 'Суммы — до вычета НДФЛ: если в тексте было «на руки», пересчитайте. Укажите обе границы или очистите обе.'
                : 'Можно не указывать. В приглашении кандидату вилка обязательна — он видит условия до начала общения.'
            }
          />
        </div>

        {error && <p className="error">{error}</p>}
        <div className="actions">
          {fromText && (
            <button type="submit" name="action" value="selection" className="button" disabled={submitting}>
              Сформировать подборку
            </button>
          )}
          <button
            type="submit"
            name="action"
            value="save"
            className={fromText ? 'button button-secondary' : 'button'}
            disabled={submitting}
          >
            {id ? 'Сохранить' : fromText ? 'Сохранить как потребность' : 'Создать потребность'}
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
