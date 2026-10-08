import { useState, type FormEvent } from 'react'
import { api, errorMessage, type Invitation, type InvitationBudget } from '../api/client'
import { dateWords } from '../candidate/words'
import { salaryWords } from '../components/salary'
import { SalaryRangeInput, type SalaryRange } from '../components/SalaryInput'
import { invitationStatusWords, isOpen } from '../invitation/words'

/**
 * Приглашение кандидату из подборки или карточки: статус последнего приглашения компании или
 * кнопка «Пригласить». Пока прошлое приглашение открыто, второе не отправить — так решает и бэкенд.
 */
export function InviteAction({
  candidateId,
  latest,
  budget,
  onSent,
}: {
  candidateId: string
  latest: Invitation | undefined
  budget: InvitationBudget | null
  onSent: (invitation: Invitation) => void
}) {
  const [open, setOpen] = useState(false)

  if (latest && isOpen(latest)) {
    return (
      <p className="hint">
        <span className="tag">приглашение {invitationStatusWords[latest.status]}</span> ·{' '}
        {salaryWords(latest.salary_from, latest.salary_to)} · ответ до {dateWords(latest.expires_at)}
      </p>
    )
  }
  if (latest?.status === 'accepted' && !latest.revoked_at) {
    return (
      <p className="success">
        Кандидат принял приглашение — имя и контакты открыты в карточке.
      </p>
    )
  }
  if (open) {
    return (
      <InviteForm
        candidateId={candidateId}
        budget={budget}
        onSent={(invitation) => {
          setOpen(false)
          onSent(invitation)
        }}
        onCancel={() => setOpen(false)}
      />
    )
  }
  const exhausted = budget !== null && budget.remaining === 0
  return (
    <div className="actions">
      <button type="button" className="button button-small" disabled={exhausted} onClick={() => setOpen(true)}>
        Пригласить
      </button>
      {latest && (
        <span className="muted">
          Прошлое приглашение {invitationStatusWords[latest.status]}
          {latest.revoked_at && ', кандидат отозвал доступ'}
        </span>
      )}
      {exhausted && budget && (
        <span className="muted">Бюджет приглашений исчерпан до {dateWords(budget.resets_at)}</span>
      )}
    </div>
  )
}

function InviteForm({
  candidateId,
  budget,
  onSent,
  onCancel,
}: {
  candidateId: string
  budget: InvitationBudget | null
  onSent: (invitation: Invitation) => void
  onCancel: () => void
}) {
  const [description, setDescription] = useState('')
  const [range, setRange] = useState<SalaryRange>({ from: '', to: '' })
  const [contact, setContact] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    const { data, error } = await api.POST('/api/employer/invitations', {
      body: {
        candidate_id: candidateId,
        description,
        salary_from: Number(range.from),
        salary_to: Number(range.to),
        contact,
      },
    })
    setSubmitting(false)
    if (data) onSent(data)
    else setError(errorMessage(error))
  }

  return (
    <form className="form invite-form" onSubmit={submit}>
      <h3>Приглашение</h3>
      <p className="hint">
        Кандидат увидит условия до начала общения: компанию, описание, вилку и способ связи. Имя и
        контакты кандидата откроются, когда он примет приглашение.
      </p>
      <label className="field">
        Что предлагаете
        <textarea
          required
          maxLength={3000}
          rows={4}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Роль, команда, задачи"
        />
      </label>
      <SalaryRangeInput range={range} onChange={setRange} />
      <label className="field">
        Способ связи
        <input
          required
          maxLength={300}
          value={contact}
          onChange={(e) => setContact(e.target.value)}
          placeholder="Telegram, почта или телефон рекрутера"
        />
      </label>
      {budget && (
        <p className="hint">
          Осталось приглашений на неделю: {budget.remaining} из {budget.limit}. Отклонённые и истёкшие
          приглашения бюджет не возвращают.
        </p>
      )}
      {error && <p className="error">{error}</p>}
      <div className="actions">
        <button type="submit" className="button button-small" disabled={submitting}>
          {submitting ? 'Отправляем…' : 'Отправить приглашение'}
        </button>
        <button type="button" className="button button-small button-secondary" onClick={onCancel}>
          Отмена
        </button>
      </div>
    </form>
  )
}
