import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { api, errorMessage, type CandidatePath, type TestItem } from '../api/client'
import { useFocusCounters } from './focus'
import { Countdown } from './protection'

// Задание создаётся при первом показе; повторный запрос отдаёт то же — часы ответа не сбросятся.
function fetchItem() {
  return api.GET('/api/candidate/path/item')
}

type Props = {
  onDone: (path: CandidatePath) => void
}

/** Попытка ещё идёт: тест на шаге `test`, незавершённый блок по теме или проверочный блок. */
function inProgress(path: CandidatePath): boolean {
  return path.stage === 'test' || path.topic_block !== null || !!path.verification?.progress
}

/**
 * Задание за заданием — у теста, блока по теме и проверочного блока. Верен ли ответ, сервер не
 * сообщает; пропустить задание нельзя. Счётчики событий — только при согласии на попытку.
 */
export function TestStep({ onDone }: Props) {
  const [item, setItem] = useState<TestItem | null>(null)
  const [response, setResponse] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [stopped, setStopped] = useState(false)
  const takeCounters = useFocusCounters(item?.focus_consent ?? false)
  const expire = useCallback(() => setStopped(true), [])

  // Не загрузилось — старое задание с экрана убираем: на него уже ответили, повторная отправка
  // получила бы отказ.
  function show({ data, error }: Awaited<ReturnType<typeof fetchItem>>) {
    // Попытка уже остановлена — например, у темы блока кончились задания: возвращаемся к пути.
    if (error?.code === 'no_test_in_progress') setStopped(true)
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

  useEffect(() => {
    if (!stopped) return
    api.GET('/api/candidate/path').then(({ data }) => {
      if (data) onDone(data)
    })
  }, [stopped, onDone])

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!item) return
    setSubmitting(true)
    setError(null)
    const { data, error } = await api.POST('/api/candidate/path/item/answer', {
      body: { presentation_id: item.id, response, ...takeCounters() },
    })
    if (!data) {
      setSubmitting(false)
      setError(errorMessage(error))
      return
    }
    if (inProgress(data)) show(await fetchItem())
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
          {item.topic_block || item.verification
            ? `Задание ${item.number} из ${item.max_items}`
            : `Задание ${item.number} · не больше ${item.max_items}`}
        </span>
        <span className="tag">{item.topic.name}</span>
        {item.verification && item.deadline && <Countdown deadline={item.deadline} onExpire={expire} />}
      </div>
      {item.number === 1 && !item.topic_block && !item.verification && (
        <p className="muted">
          Тест подбирает задания под ваш уровень и заканчивается, когда уровень определён с нужной
          точностью, — обычно раньше лимита.
        </p>
      )}
      <p className="prompt">{item.prompt}</p>
      {item.code && <pre className="code">{item.code}</pre>}
      {item.answer_format === 'choice' ? (
        <fieldset className="options">
          {item.options.map((option) => (
            <label
              key={option.letter}
              className={response === option.letter ? 'role-option selected' : 'role-option'}
            >
              <input
                type="radio"
                name="option"
                value={option.letter}
                checked={response === option.letter}
                onChange={() => setResponse(option.letter)}
              />
              <b>{option.letter}.</b> {option.text}
            </label>
          ))}
        </fieldset>
      ) : (
        <>
          {item.answer_format === 'ordering' && (
            <ul className="steps">
              {item.options.map((option) => (
                <li key={option.letter}>
                  <b>{option.letter}.</b> {option.text}
                </li>
              ))}
            </ul>
          )}
          <label className="field">
            {item.answer_format === 'ordering' ? 'Буквы шагов в верном порядке' : 'Ответ'}
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
        </>
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
