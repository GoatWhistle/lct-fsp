import { useState, type FormEvent } from 'react'
import { Link, useLocation } from 'react-router'
import { api, errorMessage, type DraftField, type NeedDraft, type OutOfCatalog } from '../api/client'
import { useEmployerCatalog } from '../employer/catalog'
import { NeedEditor, type Draft, type DraftMarks } from './NeedForm'

// Поля, которые черновик обязан заполнить, чтобы построить подборку.
const REQUIRED: DraftField[] = ['specialization', 'grade', 'work_format']

/** Черновик из текста — в поля формы; не найденное в тексте остаётся пустым и выделяется. */
function draftOfParsed(parsed: NeedDraft): { draft: Draft; marks: DraftMarks } {
  const draft: Draft = {
    title: parsed.title ?? '',
    team_description: '',
    specialization: parsed.specialization?.code ?? '',
    grade: parsed.grade?.code ?? '',
    stack: parsed.stack.map((t) => t.code),
    work_format: parsed.work_format ?? '',
    city: parsed.city ?? '',
    salary_from: parsed.salary_from?.toString() ?? '',
    salary_to: parsed.salary_to?.toString() ?? '',
    topic_importance: {},
  }
  const missing = REQUIRED.filter((field) => !(field in parsed.confidence))
  return { draft, marks: { uncertain: parsed.uncertain, missing } }
}

type Opened = { draft: Draft; marks: DraftMarks; key: number }

/** Потребность словами: текст вакансии → «система поняла так» → правка → подборка. */
export function NeedFromText() {
  const location = useLocation()
  const returned = (location.state as { draft?: Draft; marks?: DraftMarks } | null) ?? null
  const { catalog, failed } = useEmployerCatalog()
  const [text, setText] = useState('')
  const [parsing, setParsing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [outside, setOutside] = useState<OutOfCatalog | null>(null)
  // Черновик, вернувшийся с подборки, открывается сразу — правка и новая подборка.
  const [opened, setOpened] = useState<Opened | null>(() =>
    returned?.draft ? { draft: returned.draft, marks: returned.marks ?? { uncertain: [], missing: [] }, key: 0 } : null,
  )

  async function parse(event: FormEvent) {
    event.preventDefault()
    setParsing(true)
    setError(null)
    const { data, error } = await api.POST('/api/employer/needs/parse', { body: { text } })
    setParsing(false)
    if (!data) {
      setError(errorMessage(error))
      return
    }
    if (data.kind === 'out_of_catalog') {
      setOutside(data)
      setOpened(null)
      return
    }
    setOutside(null)
    setOpened({ ...draftOfParsed(data), key: (opened?.key ?? 0) + 1 })
  }

  function chooseNearest(specialization: string) {
    if (!outside) return
    const draft: Draft = {
      title: outside.asked,
      team_description: '',
      specialization,
      grade: '',
      stack: [],
      work_format: '',
      city: '',
      salary_from: '',
      salary_to: '',
      topic_importance: {},
    }
    setOpened({
      draft,
      marks: { uncertain: ['specialization'], missing: ['grade', 'work_format'] },
      key: (opened?.key ?? 0) + 1,
    })
    setOutside(null)
  }

  if (failed) return <p className="error">Не удалось загрузить справочники</p>
  if (!catalog) return <p className="muted">Загрузка…</p>

  return (
    <section className="stack">
      <div>
        <Link to="/employer">← Кабинет</Link>
      </div>
      <h1>Потребность словами</h1>
      <form onSubmit={parse} className="card form">
        <label className="field">
          Текст вакансии или кого ищете — как есть
          <textarea
            required
            rows={8}
            maxLength={20000}
            placeholder="Ищем middle QA-инженера в команду платежей: автотесты на pytest, API через Postman. Удалённо, 200–260 тыс."
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <span className="hint">
            Разбор идёт на сервере платформы, текст никуда не отправляется и не сохраняется. Система
            покажет, что поняла, — всё можно поправить.
          </span>
        </label>
        {error && <p className="error">{error}</p>}
        <div className="actions">
          <button type="submit" className="button" disabled={parsing}>
            {parsing ? 'Разбираем…' : 'Разобрать'}
          </button>
          <Link to="/employer/needs/new">Заполнить форму вручную</Link>
        </div>
      </form>

      {outside && (
        <div className="card">
          <h2>Такой специализации нет</h2>
          <p>
            {outside.asked ? `«${outside.asked}» — ` : ''}не наше направление: тест и категории есть только по
            специализациям справочника, подборка по ним была бы пустой. Ближайшие:
          </p>
          <div className="actions">
            {outside.nearest.map((s) => (
              <button
                key={s.code}
                type="button"
                className="button button-secondary"
                onClick={() => chooseNearest(s.code)}
              >
                {s.name}
              </button>
            ))}
          </div>
        </div>
      )}

      {opened && (
        <>
          <h2>Система поняла так</h2>
          <p className="hint">
            Выделенное проверьте: в этих полях система не уверена или не нашла их в тексте. Важность тем
            выводится из стека. «Сформировать подборку» не сохраняет потребность — можно вернуться,
            поправить и построить новую.
          </p>
          <NeedEditor
            key={opened.key}
            catalog={catalog}
            need={null}
            initial={opened.draft}
            marks={opened.marks}
          />
        </>
      )}
    </section>
  )
}
