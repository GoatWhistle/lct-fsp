import { useState } from 'react'
import { api, errorCode, errorMessage, type CandidatePath } from '../api/client'
import { gradeName, type Catalog } from './catalog'
import { TestStep } from './TestStep'
import { dateTimeWords } from './words'

type Props = { catalog: Catalog; path: CandidatePath; onChange: (path: CandidatePath) => void }

type Verification = NonNullable<CandidatePath['verification']>

const expectedWords = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 })

/** Причина расхождения числами: «ожидалось около 7 верных из 10, получено 2». */
function reason(last: NonNullable<Verification['last']>): string {
  return (
    `По основному тесту ожидалось около ${expectedWords.format(last.expected)} верных из ` +
    `${last.items}, получено ${last.correct}.`
  )
}

/** Ошибка API словами; у повтора блока — с датой, когда можно. */
function failure(error: unknown): string {
  if (errorCode(error) === 'verification_too_early' && error && typeof error === 'object') {
    const at = 'available_at' in error && typeof error.available_at === 'string' ? error.available_at : null
    if (at) return `Повторный блок станет доступен ${dateTimeWords(at)}.`
  }
  return errorMessage(error)
}

/**
 * Проверочный блок: короткий блок на время из невиданных заданий тех же тем. Нужен, когда
 * результат попытки ждёт его, или добровольно — подтвердить уровень категории. Флаги, из-за которых
 * его предложили, не показываются и сами ничего не понижают.
 */
export function VerificationCard({ catalog, path, onChange }: Props) {
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const verification = path.verification
  if (!verification) return null

  if (verification.progress) {
    return (
      <section className="stack">
        <h2>Проверочный блок</h2>
        <p className="lead">
          {verification.progress.items} заданий на время — до{' '}
          {dateTimeWords(verification.progress.deadline)}. Неотвеченное к сроку считается неверным.
        </p>
        <TestStep onDone={onChange} />
      </section>
    )
  }

  async function start() {
    setSubmitting(true)
    setError(null)
    const { data, error } = await api.POST('/api/candidate/path/verification')
    setSubmitting(false)
    if (data) onChange(data)
    else setError(failure(error))
  }

  const last = verification.last
  const pending = verification.grade
  return (
    <div className="card form">
      <h2>Проверочный блок</h2>
      {pending ? (
        <p>
          Результат на {gradeName(catalog, pending)} нужно подтвердить коротким блоком: задания тех
          же тем, которых вы ещё не видели, на время. Совпадёт с основным тестом — категория{' '}
          {path.category ? 'повысится' : 'будет присвоена'} с пометкой «уровень подтверждён». Это
          не штраф: сигналы, из-за которых блок предложен, категорию не понижают и работодателю не
          видны.
        </p>
      ) : (
        <p>
          Можно подтвердить уровень категории коротким блоком на время. Совпадёт с тестом —
          работодатели увидят пометку «подтверждено проверочным блоком». Не совпадёт — категория не
          изменится.
        </p>
      )}
      {last && !last.confirmed && (
        <p className="error">
          Блок разошёлся с тестом. {reason(last)}
          {pending && path.stage === 'verification' && ' Можно пройти блок ещё раз или начать тест на грейд ниже.'}
        </p>
      )}
      {verification.available_at && (
        <p className="hint">Повторный блок станет доступен {dateTimeWords(verification.available_at)}.</p>
      )}
      {error && <p className="error">{error}</p>}
      <div className="actions">
        <button
          type="button"
          className="button"
          disabled={submitting || verification.available_at !== null}
          onClick={start}
        >
          {last ? 'Пройти блок ещё раз' : 'Начать проверочный блок'}
        </button>
      </div>
    </div>
  )
}
