import { useEffect, useState } from 'react'
import { api, errorMessage, type FspAchievement, type FspStatus } from '../api/client'
import { fspResultWords, goToFspId } from './fsp'
import { dateTimeWords, dateWords, oneDecimal } from './words'

/**
 * Блок «ФСП ID» в профиле кандидата: привязка, подтверждённые достижения с датой снимка реестра,
 * обновление и отвязка. Расхождение ФСП и теста видит только сам кандидат.
 */
export function FspCard({ notice, returnError }: { notice: string | null; returnError: string | null }) {
  const [status, setStatus] = useState<FspStatus | null>(null)
  const [error, setError] = useState<string | null>(returnError)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.GET('/api/candidate/fsp').then(({ data, error }) => {
      if (data) setStatus(data)
      else setError(errorMessage(error))
    })
  }, [])

  async function link() {
    setBusy(true)
    setError(null)
    const failed = await goToFspId('link')
    if (failed) {
      setError(failed)
      setBusy(false)
    }
  }

  async function refresh() {
    setBusy(true)
    setError(null)
    const { data, error } = await api.POST('/api/candidate/fsp/refresh')
    setBusy(false)
    if (data) setStatus(data)
    else setError(errorMessage(error))
  }

  async function unlink() {
    if (!window.confirm('Отвязать ФСП ID? Достижения и их вклад уйдут из профиля навыков.')) return
    setBusy(true)
    setError(null)
    const { data, error } = await api.DELETE('/api/candidate/fsp')
    setBusy(false)
    if (data) setStatus(data)
    else setError(errorMessage(error))
  }

  return (
    <div className="card form">
      <div className="section-head">
        <h2>ФСП ID</h2>
        {status?.linked && (
          <div className="actions">
            <button type="button" className="button button-small" disabled={busy} onClick={refresh}>
              Обновить достижения
            </button>
            {status.can_unlink && (
              <button
                type="button"
                className="button button-small button-secondary"
                disabled={busy}
                onClick={unlink}
              >
                Отвязать
              </button>
            )}
          </div>
        )}
      </div>
      {notice && <p className="success">{notice}</p>}
      {error && <p className="error">{error}</p>}
      {!status && !error && <p className="muted">Загрузка…</p>}
      {status && !status.linked && (
        <>
          <p>
            Результаты соревнований ФСП — самый весомый сигнал профиля: их нельзя нагуглить или
            сгенерировать. Привяжите ФСП ID, и победы, призовые места и финалы войдут в профиль
            навыков.
          </p>
          <p className="hint">Нет ФСП ID — не страшно: профиль строится по тесту, штрафа нет.</p>
          <div className="actions">
            <button type="button" className="button" disabled={busy} onClick={link}>
              Привязать ФСП ID
            </button>
          </div>
        </>
      )}
      {status?.linked && <Linked status={status} />}
    </div>
  )
}

function Linked({ status }: { status: FspStatus }) {
  return (
    <>
      <p className="muted">
        {status.fetched_at
          ? `Достижения из реестра ФСП на ${dateTimeWords(status.fetched_at)}`
          : 'Реестр ФСП ещё не ответил — нажмите «Обновить достижения» позже'}
      </p>
      {status.achievements.length === 0 ? (
        <p>Нет истории ФСП — профиль строится по тесту, это не штраф.</p>
      ) : (
        <table className="table">
          <tbody>
            {status.achievements.map((a, i) => (
              <tr key={i}>
                <td className="muted">{dateWords(a.date)}</td>
                <th scope="row">
                  {a.event}
                  <span className="hint importance-source">{a.discipline.name}</span>
                </th>
                <td>{achievementWords(a)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {status.divergences.length > 0 && (
        <div className="stack">
          <p>
            <strong>Тест ниже ваших результатов ФСП.</strong> Рекомендуем пройти проверочный блок:
            он подтвердит уровень. Профиль навыков от этого не понижается, работодатель пометку не
            видит.
          </p>
          <ul className="upcoming">
            {status.divergences.map((d) => (
              <li key={d.topic.code}>
                {d.topic.name}: тест — {oneDecimal.format(d.test_level)}, результат «
                {fspResultWords[d.result]}» в дисциплине «{d.discipline.name}» —{' '}
                {oneDecimal.format(d.result_level)}
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="hint">
        Работодатель до принятия приглашения видит только тип результата, дисциплину и год; мероприятие,
        место и команду — после. В PDF-профиле достижения — полностью, отдельно от самоописания.
      </p>
    </>
  )
}

function achievementWords(a: FspAchievement): string {
  const parts = [fspResultWords[a.result]]
  if (a.place !== null) parts.push(`${a.place} место`)
  if (a.team_role) parts.push(`в команде — ${a.team_role.name}`)
  return parts.join(', ')
}
