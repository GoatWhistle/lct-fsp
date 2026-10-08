import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api, errorMessage, type CandidatePath, type Feedback, type FeedbackHint } from '../api/client'
import { dateTimeWords, oneDecimal } from './words'

type StartBlock = (path: CandidatePath) => void

/**
 * Обратная связь по подборкам: сколько раз кандидат попал в подборки за период, медианное место
 * и что поднимет выше. Работодатели и их потребности не раскрываются; пока компаний мало, есть
 * только общая подсказка.
 */
export function FeedbackCard({ onStartBlock }: { onStartBlock: StartBlock }) {
  const [feedback, setFeedback] = useState<Feedback | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.GET('/api/candidate/feedback').then(({ data, error }) => {
      if (data) setFeedback(data)
      else setError(errorMessage(error))
    })
  }, [])

  if (error) return <p className="error">Обратная связь не загрузилась: {error}</p>
  if (!feedback) return null
  const { placement } = feedback
  return (
    <div className="card">
      <h2>Обратная связь</h2>
      {placement ? (
        <p>
          Подборок с вами за {feedback.period_days} дней — {placement.selections}. Медианное место —{' '}
          <strong>{oneDecimal.format(placement.median_position)}</strong>, в точном блоке —{' '}
          {Math.round(placement.exact_share * 100)} % подборок.
        </p>
      ) : (
        <p>
          Подборок с вами за {feedback.period_days} дней пока мало, чтобы показать место: так
          работодатели и их потребности остаются нераскрытыми.
        </p>
      )}
      {feedback.hints.length > 0 && (
        <>
          <h3>{placement ? 'Что поднимет выше' : 'Что можно сделать'}</h3>
          <ul className="stack">
            {feedback.hints.map((h) => (
              <li key={h.topic?.code ?? h.action.kind}>
                <HintView hint={h} onStartBlock={onStartBlock} />
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}

type HintProps = { hint: FeedbackHint; onStartBlock: StartBlock }

function HintView({ hint, onStartBlock }: HintProps) {
  if (hint.action.kind === 'link_fsp') {
    return (
      <span>
        Привяжите ФСП ID — результаты соревнований станут самым весомым сигналом профиля. Без них
        штрафа нет. <Link to="/candidate/profile">В профиль</Link>
      </span>
    )
  }
  const topic = hint.topic?.name ?? ''
  const what =
    hint.scenario === 'raise'
      ? `Подтянуть уровень по теме «${topic}»`
      : hint.scenario === 'narrow'
        ? `Уточнить уровень по теме «${topic}»`
        : `Уточнить уровень по теме «${topic}» — здесь погрешность профиля наибольшая`
  return (
    <span>
      {what}
      {hint.gain !== null && (
        <>
          : соответствие потребностям +{Math.round(hint.gain * 100)} п. п.
          {hint.places !== null && hint.places > 0 && (
            <>, в среднем на {oneDecimal.format(hint.places)} места выше</>
          )}
        </>
      )}
      . <ActionView hint={hint} onStartBlock={onStartBlock} />
    </span>
  )
}

function ActionView({ hint, onStartBlock }: HintProps) {
  if (hint.action.kind === 'regular_task') {
    return <Link to="/candidate/tasks">Ответить на регулярное задание</Link>
  }
  return <TopicBlockAction hint={hint} onStartBlock={onStartBlock} />
}

/** Блок по теме: короткий тест по одной теме, не чаще установленного срока на тему. */
function TopicBlockAction({ hint, onStartBlock }: HintProps) {
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const topic = hint.topic?.code ?? ''

  async function start() {
    setSubmitting(true)
    setError(null)
    const { data, error } = await api.POST('/api/candidate/path/topic-block', { body: { topic } })
    setSubmitting(false)
    if (data) onStartBlock(data)
    else setError(errorMessage(error))
  }

  if (!hint.action.available) {
    return (
      <span className="muted">
        Блок по теме — можно с {hint.action.available_at ? dateTimeWords(hint.action.available_at) : 'даты повтора'}.
      </span>
    )
  }
  return (
    <>
      <button type="button" className="button button-small" disabled={submitting} onClick={start}>
        Пройти блок по теме
      </button>
      {error && <span className="error"> {error}</span>}
    </>
  )
}
