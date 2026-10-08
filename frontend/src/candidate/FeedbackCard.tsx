import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api, errorMessage, type Feedback, type FeedbackHint } from '../api/client'
import { oneDecimal } from './words'

/**
 * Обратная связь по подборкам: сколько раз кандидат попал в подборки за период, медианное место
 * и что поднимет выше. Работодатели и их потребности не раскрываются; пока компаний мало, есть
 * только общая подсказка.
 */
export function FeedbackCard() {
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
                <HintView hint={h} />
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}

function HintView({ hint }: { hint: FeedbackHint }) {
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
      . <ActionView hint={hint} />
    </span>
  )
}

function ActionView({ hint }: { hint: FeedbackHint }) {
  if (hint.action.kind === 'regular_task') {
    return <Link to="/candidate/tasks">Ответить на регулярное задание</Link>
  }
  return hint.action.available ? (
    <span>Пройдите блок по теме.</span>
  ) : (
    <span className="muted">Блок по теме скоро появится.</span>
  )
}
