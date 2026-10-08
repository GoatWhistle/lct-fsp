import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { api, errorMessage, type CatalogTask, type OwnAnswer } from '../api/client'
import { useCatalog } from '../candidate/catalog'
import { dateTimeWords } from '../candidate/words'

const statusWords: Record<OwnAnswer['status'], string> = {
  accepted: 'Ответ принят и учтён в профиле',
  awaiting_review: 'Ждёт оценки автора',
  reviewed: 'Оценён и учтён в профиле',
}

/** Каталог регулярных заданий специализации кандидата — всех грейдов, по одному ответу на задание. */
export function TaskCatalog() {
  const { catalog, failed } = useCatalog()
  const [grade, setGrade] = useState('')
  const [topic, setTopic] = useState('')
  const [tasks, setTasks] = useState<CatalogTask[] | null>(null)
  const [answers, setAnswers] = useState<OwnAnswer[]>([])
  const [specialization, setSpecialization] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Счётчик запросов: ответ на прежний фильтр, пришедший позже, список не перезаписывает.
  const latest = useRef(0)

  const load = useCallback(() => {
    const request = ++latest.current
    const query = { grade: grade || undefined, topic: topic || undefined }
    Promise.all([
      api.GET('/api/candidate/tasks', { params: { query } }),
      api.GET('/api/candidate/tasks/answers'),
    ]).then(([catalog, own]) => {
      if (request !== latest.current) return
      if (catalog.error || own.error) {
        setError(errorMessage(catalog.error ?? own.error))
        return
      }
      setTasks(catalog.data ?? [])
      setAnswers(own.data ?? [])
    })
  }, [grade, topic])

  useEffect(load, [load])

  useEffect(() => {
    api.GET('/api/candidate/path').then(({ data }) => setSpecialization(data?.category?.specialization.code ?? null))
  }, [])

  if (error || failed) {
    return (
      <section className="stack">
        <h1>Регулярные задания</h1>
        <p className="error">{error ?? 'Не удалось загрузить справочники'}</p>
        <p>
          <Link to="/candidate">← В кабинет</Link>
        </p>
      </section>
    )
  }
  if (!tasks || !catalog) return <p className="muted">Загрузка…</p>
  const topics = catalog.specializations.find((s) => s.code === specialization)?.topics ?? []

  return (
    <section className="stack">
      <h1>Регулярные задания</h1>
      <p className="lead">
        Задачи работодателей по вашей специализации, любого грейда. Берите сколько хотите — на
        каждое отвечаете один раз. Ответ уточняет профиль навыков по темам задания и показывает, что
        уровень недавно подтверждён. Категорию задания не меняют.
      </p>
      <div className="card field-row">
        <label className="field">
          Грейд
          <select value={grade} onChange={(e) => setGrade(e.target.value)}>
            <option value="">Все</option>
            {catalog.grades.map((g) => (
              <option key={g.code} value={g.code}>
                {g.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Тема
          <select value={topic} onChange={(e) => setTopic(e.target.value)}>
            <option value="">Все</option>
            {topics.map((t) => (
              <option key={t.code} value={t.code}>
                {t.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      {tasks.length === 0 ? (
        <div className="card">
          <p>Подходящих заданий пока нет — загляните позже.</p>
        </div>
      ) : (
        tasks.map((task) => <TaskItem key={task.id} task={task} onAnswered={load} />)
      )}
      {answers.length > 0 && (
        <section className="stack">
          <h2>Ваши ответы</h2>
          {answers.map((a) => (
            <article key={a.task.id} className="card">
              <span className="muted">
                {a.task.grade.name} · {a.task.topics.map((t) => t.name).join(', ')} · {dateTimeWords(a.answered_at)}
              </span>
              <p className="prewrap">{a.task.prompt}</p>
              <p className="prewrap">
                <strong>Ваш ответ:</strong> {a.response}
              </p>
              <span className="tag">{statusWords[a.status]}</span>
            </article>
          ))}
        </section>
      )}
      <p>
        <Link to="/candidate">← В кабинет</Link>
      </p>
    </section>
  )
}

function TaskItem({ task, onAnswered }: { task: CatalogTask; onAnswered: () => void }) {
  const [response, setResponse] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    const { data, error } = await api.POST('/api/candidate/tasks/{task_id}/answer', {
      params: { path: { task_id: task.id } },
      body: { response },
    })
    setSubmitting(false)
    if (data) onAnswered()
    else setError(errorMessage(error))
  }

  return (
    <article className="card form">
      <span className="muted">
        {task.grade.name} · {task.topics.map((t) => t.name).join(', ')} ·{' '}
        {task.kind === 'reference' ? 'короткий ответ' : 'развёрнутый ответ, оценит автор'} · ответов: {task.answers}
      </span>
      <p className="prewrap">{task.prompt}</p>
      {task.answered ? (
        <span className="tag">Вы уже ответили</span>
      ) : (
        <form onSubmit={submit} className="form">
          <label className="field">
            Ответ
            {task.kind === 'reference' ? (
              <input required maxLength={4000} value={response} onChange={(e) => setResponse(e.target.value)} />
            ) : (
              <textarea
                required
                maxLength={4000}
                rows={5}
                value={response}
                onChange={(e) => setResponse(e.target.value)}
              />
            )}
          </label>
          {error && <p className="error">{error}</p>}
          <div className="actions">
            <button type="submit" className="button button-small" disabled={submitting}>
              Ответить
            </button>
            <span className="hint">Ответ — один раз, изменить его нельзя</span>
          </div>
        </form>
      )}
    </article>
  )
}
