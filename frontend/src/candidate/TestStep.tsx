import { useEffect, useState, type FormEvent } from 'react'
import { api, errorMessage, type CandidatePath, type TestItem } from '../api/client'

// Задание создаётся при первом показе; повторный запрос отдаёт то же — часы ответа не сбросятся.
function fetchItem() {
  return api.GET('/api/candidate/path/item')
}

type Props = {
  onDone: (path: CandidatePath) => void
}

/** Задание за заданием. Верен ли ответ, сервер не сообщает; пропустить задание нельзя. */
export function TestStep({ onDone }: Props) {
  const [item, setItem] = useState<TestItem | null>(null)
  const [response, setResponse] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  // Не загрузилось — старое задание с экрана убираем: на него уже ответили, повторная отправка
  // получила бы отказ.
  function show({ data, error }: Awaited<ReturnType<typeof fetchItem>>) {
    setItem(data ?? null)
    setResponse('')
    setError(data ? null : errorMessage(error))
  }

  async function retry() {
    setError(null)
    show(await fetchItem())
  }

  useEffect(() => {
    fetchItem().then(show)
  }, [])

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!item) return
    setSubmitting(true)
    setError(null)
    const { data, error } = await api.POST('/api/candidate/path/item/answer', {
      body: { presentation_id: item.id, response },
    })
    if (!data) {
      setSubmitting(false)
      setError(errorMessage(error))
      return
    }
    if (data.stage === 'test') show(await fetchItem())
    else onDone(data)
    setSubmitting(false)
  }

  if (!item) {
    if (!error) return <p className="muted">Загрузка задания…</p>
    return (
      <div className="card form">
        <p className="error">{error}</p>
        <div className="actions">
          <button type="button" className="button" onClick={retry}>
            Повторить
          </button>
        </div>
      </div>
    )
  }

  return (
    <form onSubmit={submit} className="card form">
      <div className="item-head">
        <span className="muted">
          Задание {item.number} · не больше {item.max_items}
        </span>
        <span className="tag">{item.topic.name}</span>
      </div>
      {item.number === 1 && (
        <p className="muted">
          Тест подбирает задания под ваш уровень и заканчивается, когда уровень определён с нужной
          точностью, — обычно раньше лимита.
        </p>
      )}
      <p className="prompt">{item.prompt}</p>
      {item.code && <pre className="code">{item.code}</pre>}
      {item.options.length > 0 ? (
        <fieldset className="options">
          {item.options.map((option) => (
            <label key={option} className={response === option ? 'role-option selected' : 'role-option'}>
              <input
                type="radio"
                name="option"
                value={option}
                checked={response === option}
                onChange={() => setResponse(option)}
              />
              {option}
            </label>
          ))}
        </fieldset>
      ) : (
        <label className="field">
          Ответ
          <input
            required
            maxLength={500}
            autoComplete="off"
            spellCheck={false}
            autoFocus
            value={response}
            onChange={(e) => setResponse(e.target.value)}
          />
        </label>
      )}
      {error && <p className="error">{error}</p>}
      <div className="actions">
        <button type="submit" className="button" disabled={submitting || !response.trim()}>
          {item.number === item.max_items ? 'Ответить и завершить' : 'Ответить'}
        </button>
      </div>
    </form>
  )
}
