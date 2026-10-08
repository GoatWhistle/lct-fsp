import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import {
  api,
  errorCode,
  errorMessage,
  type AuthorAnswer,
  type RegularTask,
  type TaskInput,
  type TaskKind,
} from '../api/client'
import { dateTimeWords } from '../candidate/words'
import { useEmployerCatalog, type EmployerCatalog } from '../employer/catalog'

const MAX_TOPICS = 3

const kindWords: Record<TaskKind, string> = {
  reference: 'С эталоном',
  open: 'Открытое',
}

const rubric = [
  { value: 0, title: '0', hint: 'не решено или не по делу' },
  { value: 1, title: '1', hint: 'частично, подход с ошибками' },
  { value: 2, title: '2', hint: 'верно в целом' },
  { value: 3, title: '3', hint: 'верно и хорошо: оптимально, с разбором краёв' },
]

function emptyForm(catalog: EmployerCatalog): TaskInput {
  return {
    specialization: catalog.specializations[0]?.code ?? '',
    grade: catalog.grades.find((g) => g.code === 'middle')?.code ?? catalog.grades[0]?.code ?? '',
    kind: 'reference',
    prompt: '',
    topics: [],
    reference_answer: '',
  }
}

/** Регулярные задания работодателя: публикация, ответы кандидатов и оценка открытых. */
export function EmployerTasks() {
  const { catalog, failed } = useEmployerCatalog()
  const [tasks, setTasks] = useState<RegularTask[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.GET('/api/employer/tasks').then(({ data, error }) => {
      if (data) setTasks(data)
      else setError(errorMessage(error))
    })
  }, [])

  if (error || failed) return <p className="error">{error ?? 'Не удалось загрузить справочники'}</p>
  if (!tasks || !catalog) return <p className="muted">Загрузка…</p>

  function replace(task: RegularTask) {
    setTasks((current) => (current ?? []).map((t) => (t.id === task.id ? task : t)))
  }

  return (
    <section className="stack">
      <h1>Регулярные задания</h1>
      <p className="lead">
        Короткие задачи для категории. Кандидаты специализации берут их сами из каталога и
        отвечают по одному разу. Ответ сужает погрешность профиля кандидата по темам задания —
        его видят все работодатели как «подтверждено регулярным заданием», а сам ответ — только
        вы, без имени и контактов.
      </p>
      <TaskForm catalog={catalog} onCreated={(task) => setTasks([task, ...tasks])} />
      {tasks.length > 0 && (
        <section className="stack">
          <h2>Ваши задания</h2>
          {tasks.map((task) => (
            <TaskCard key={task.id} task={task} onChange={replace} />
          ))}
        </section>
      )}
      <p>
        <Link to="/employer">← В кабинет</Link>
      </p>
    </section>
  )
}

function TaskForm({ catalog, onCreated }: { catalog: EmployerCatalog; onCreated: (task: RegularTask) => void }) {
  const [form, setForm] = useState<TaskInput>(() => emptyForm(catalog))
  const [error, setError] = useState<string | null>(null)
  const [needsCompany, setNeedsCompany] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const topics = catalog.specializations.find((s) => s.code === form.specialization)?.topics ?? []

  function set<K extends keyof TaskInput>(key: K, value: TaskInput[K]) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  function toggleTopic(code: string) {
    const chosen = form.topics.includes(code)
      ? form.topics.filter((t) => t !== code)
      : form.topics.length < MAX_TOPICS
        ? [...form.topics, code]
        : form.topics
    set('topics', chosen)
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    const body = { ...form, reference_answer: form.kind === 'reference' ? form.reference_answer : null }
    const { data, error } = await api.POST('/api/employer/tasks', { body })
    setSubmitting(false)
    if (data) {
      onCreated(data)
      setForm(emptyForm(catalog))
    } else {
      setNeedsCompany(errorCode(error) === 'company_required')
      setError(errorMessage(error))
    }
  }

  return (
    <form onSubmit={submit} className="card form">
      <h2>Новое задание</h2>
      <div className="field-row">
        <label className="field">
          Специализация
          <select
            value={form.specialization}
            onChange={(e) => setForm({ ...form, specialization: e.target.value, topics: [] })}
          >
            {catalog.specializations.map((s) => (
              <option key={s.code} value={s.code}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Грейд
          <select value={form.grade} onChange={(e) => set('grade', e.target.value)}>
            {catalog.grades.map((g) => (
              <option key={g.code} value={g.code}>
                {g.name}
              </option>
            ))}
          </select>
          <span className="hint">От грейда — сложность: верный ответ на задачу старше весит больше</span>
        </label>
      </div>
      <div className="field">
        Темы — от 1 до {MAX_TOPICS}
        <div className="chips">
          {topics.map((t) => (
            <button
              key={t.code}
              type="button"
              className={form.topics.includes(t.code) ? 'chip chip-toggle selected' : 'chip chip-toggle'}
              aria-pressed={form.topics.includes(t.code)}
              onClick={() => toggleTopic(t.code)}
            >
              {t.name}
            </button>
          ))}
        </div>
      </div>
      <label className="field">
        Условие
        <textarea required maxLength={4000} rows={5} value={form.prompt} onChange={(e) => set('prompt', e.target.value)} />
      </label>
      <div className="field">
        Как проверять
        <div className="segmented" role="group" aria-label="Вид задания">
          {(['reference', 'open'] as const).map((kind) => (
            <button
              key={kind}
              type="button"
              className={form.kind === kind ? 'selected' : ''}
              aria-pressed={form.kind === kind}
              onClick={() => set('kind', kind)}
            >
              {kindWords[kind]}
            </button>
          ))}
        </div>
        <span className="hint">
          {form.kind === 'reference'
            ? 'Ответ — строка или число, его сверяет система. Кандидат вердикт не увидит.'
            : 'Скрипт, бизнес-решение: ответ оцениваете вы по рубрике 0–3.'}
        </span>
      </div>
      {form.kind === 'reference' && (
        <label className="field">
          Эталон
          <input
            required
            maxLength={200}
            value={form.reference_answer ?? ''}
            onChange={(e) => set('reference_answer', e.target.value)}
          />
        </label>
      )}
      {error && (
        <p className="error">
          {error}
          {needsCompany && (
            <>
              {' '}
              <Link to="/employer/company">Заполнить профиль компании</Link>
            </>
          )}
        </p>
      )}
      <div className="actions">
        <button type="submit" className="button" disabled={submitting || form.topics.length === 0}>
          Опубликовать
        </button>
      </div>
    </form>
  )
}

function TaskCard({ task, onChange }: { task: RegularTask; onChange: (task: RegularTask) => void }) {
  const [answers, setAnswers] = useState<AuthorAnswer[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  function load(open: boolean) {
    if (!open || answers) return
    api
      .GET('/api/employer/tasks/{task_id}/answers', { params: { path: { task_id: task.id } } })
      .then(({ data, error }) => {
        if (data) setAnswers(data)
        else setError(errorMessage(error))
      })
  }

  async function withdraw() {
    const { data, error } = await api.POST('/api/employer/tasks/{task_id}/withdraw', {
      params: { path: { task_id: task.id } },
    })
    if (data) onChange(data)
    else setError(errorMessage(error))
  }

  function graded(answer: AuthorAnswer) {
    setAnswers((current) => (current ?? []).map((a) => (a.id === answer.id ? answer : a)))
  }

  return (
    <article className="card">
      <div className="section-head">
        <div>
          <span className="muted">
            {task.specialization.name} · {task.grade.name} · {kindWords[task.kind].toLowerCase()}
            {task.withdrawn_at && ' · снято'}
          </span>
          <h3>{task.topics.map((t) => t.name).join(', ')}</h3>
        </div>
        {!task.withdrawn_at && (
          <button type="button" className="button button-small button-secondary" onClick={withdraw}>
            Снять
          </button>
        )}
      </div>
      <p className="prewrap">{task.prompt}</p>
      {task.reference_answer && <p className="muted">Эталон: {task.reference_answer}</p>}
      {error && <p className="error">{error}</p>}
      <details onToggle={(e) => load(e.currentTarget.open)}>
        <summary>Ответы: {task.answers}</summary>
        {answers === null ? (
          <p className="muted">Загрузка…</p>
        ) : answers.length === 0 ? (
          <p className="muted">Пока никто не ответил</p>
        ) : (
          answers.map((answer) => (
            <AnswerRow key={answer.id} task={task} answer={answer} onGraded={graded} />
          ))
        )}
      </details>
    </article>
  )
}

function AnswerRow({
  task,
  answer,
  onGraded,
}: {
  task: RegularTask
  answer: AuthorAnswer
  onGraded: (answer: AuthorAnswer) => void
}) {
  const [error, setError] = useState<string | null>(null)

  async function grade(value: number) {
    const { data, error } = await api.POST('/api/employer/tasks/{task_id}/answers/{answer_id}/grade', {
      params: { path: { task_id: task.id, answer_id: answer.id } },
      body: { rubric: value },
    })
    if (data) onGraded(data)
    else setError(errorMessage(error))
  }

  return (
    <div className="stack">
      <span className="muted">
        {answer.candidate} · {dateTimeWords(answer.answered_at)}
      </span>
      <p className="prewrap">{answer.response}</p>
      {task.kind === 'reference' ? (
        <p className={answer.correct ? 'success' : 'muted'}>{answer.correct ? 'Совпал с эталоном' : 'Не совпал с эталоном'}</p>
      ) : answer.rubric !== null ? (
        <p className="muted">
          Оценка {answer.rubric} — {rubric[answer.rubric].hint}
        </p>
      ) : (
        <div className="segmented" role="group" aria-label="Оценка по рубрике">
          {rubric.map((r) => (
            <button key={r.value} type="button" title={r.hint} onClick={() => grade(r.value)}>
              {r.title}
            </button>
          ))}
        </div>
      )}
      {error && <p className="error">{error}</p>}
    </div>
  )
}
