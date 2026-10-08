import { useCallback, useEffect, useState } from 'react'
import { api, errorCode, errorMessage, type Invitation } from '../api/client'
import { salaryWords } from '../components/salary'
import { Conversation } from '../invitation/Conversation'
import { invitationStatusWords, isOpen } from '../invitation/words'
import { dateTimeWords, dateWords } from './words'

/**
 * Входящие приглашения: условия видны до начала общения. Открытие помечает приглашение
 * просмотренным; принятое открывает компании имя, контакты и профиль, кроме ожидаемой зарплаты,
 * и переписку с ней. Доступ к данным можно отозвать — переписка останется.
 */
const STALE = new Set(['invitation_expired', 'invitation_transition_not_allowed'])

export function Inbox({ onRead }: { onRead: () => void }) {
  const [invitations, setInvitations] = useState<Invitation[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    api.GET('/api/candidate/invitations').then(({ data, error }) => {
      if (data) setInvitations(data)
      else setError(errorMessage(error))
    })
  }, [])

  useEffect(load, [load])

  const read = useCallback(
    (invitationId: string) => {
      setInvitations((current) => current?.map((i) => (i.id === invitationId ? { ...i, unread_messages: 0 } : i)) ?? null)
      onRead()
    },
    [onRead],
  )

  function replace(next: Invitation) {
    setInvitations((current) => current?.map((i) => (i.id === next.id ? next : i)) ?? null)
  }

  if (error) return <p className="error">Приглашения не загрузились: {error}</p>
  if (!invitations) return null
  return (
    <section className="stack">
      <h2>Приглашения</h2>
      {invitations.length === 0 ? (
        <div className="card">
          <p>
            Приглашений пока нет. Работодатели находят вас в подборках по категории и профилю
            навыков — имя и контакты они увидят, только если вы примете приглашение.
          </p>
        </div>
      ) : (
        invitations.map((i) => (
          <InvitationCard key={i.id} invitation={i} onChange={replace} onStale={load} onRead={read} />
        ))
      )}
    </section>
  )
}

function InvitationCard({
  invitation,
  onChange,
  onStale,
  onRead,
}: {
  invitation: Invitation
  onChange: (invitation: Invitation) => void
  /** Статус на экране устарел — истёк срок или ответ уже записан: перечитать входящие. */
  onStale: () => void
  onRead: (invitationId: string) => void
}) {
  const [busy, setBusy] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [confirmRevoke, setConfirmRevoke] = useState(false)
  const markRead = useCallback(() => onRead(invitation.id), [onRead, invitation.id])
  const [error, setError] = useState<string | null>(null)
  const params = { params: { path: { invitation_id: invitation.id } } }

  async function run(request: () => Promise<{ data?: Invitation; error?: unknown }>) {
    setBusy(true)
    setError(null)
    const { data, error } = await request()
    setBusy(false)
    if (data) onChange(data)
    else {
      setError(errorMessage(error))
      if (STALE.has(errorCode(error) ?? '')) onStale()
    }
  }

  function toggle(open: boolean) {
    setExpanded(open)
    if (open && invitation.status === 'sent') {
      run(() => api.POST('/api/candidate/invitations/{invitation_id}/view', params))
    }
  }

  const open = isOpen(invitation)
  return (
    <details className={`card invitation-card${invitation.status === 'sent' ? ' unread' : ''}`} onToggle={(e) => toggle(e.currentTarget.open)}>
      <summary>
        <strong>{invitation.company_name}</strong> · {salaryWords(invitation.salary_from, invitation.salary_to)}{' '}
        <span className={invitation.status === 'sent' ? 'tag' : 'muted'}>
          {invitation.status === 'sent' ? 'новое' : invitationStatusWords[invitation.status]}
        </span>
        {invitation.unread_messages > 0 && <> <span className="tag">сообщений: {invitation.unread_messages}</span></>}
      </summary>
      <p className="prewrap">{invitation.description}</p>
      <p>
        Вилка: <strong>{salaryWords(invitation.salary_from, invitation.salary_to)}</strong>
      </p>
      <p>Способ связи: {invitation.contact}</p>
      <p className="muted">
        Получено {dateTimeWords(invitation.sent_at)}
        {open && ` · ответить до ${dateWords(invitation.expires_at)}`}
        {invitation.answered_at && ` · ответ ${dateTimeWords(invitation.answered_at)}`}
      </p>
      {invitation.status === 'accepted' && !invitation.revoked_at && (
        <>
          <p className="success">Вы приняли приглашение — компании открыты ваше имя, контакты и профиль.</p>
          {confirmRevoke ? (
            <div className="actions">
              <span className="hint">
                Компания снова увидит обезличенную карточку. Вернуть доступ можно, только приняв её новое приглашение.
              </span>
              <button
                type="button"
                className="button button-small"
                disabled={busy}
                onClick={() => run(() => api.POST('/api/candidate/invitations/{invitation_id}/revoke', params))}
              >
                Отозвать
              </button>
              <button type="button" className="button button-small button-secondary" onClick={() => setConfirmRevoke(false)}>
                Оставить
              </button>
            </div>
          ) : (
            <div className="actions">
              <button type="button" className="button button-small button-secondary" onClick={() => setConfirmRevoke(true)}>
                Отозвать доступ
              </button>
            </div>
          )}
        </>
      )}
      {invitation.revoked_at && (
        <p className="hint">
          Доступ отозван {dateTimeWords(invitation.revoked_at)}: компания видит обезличенную карточку без имени и
          контактов. Переписка продолжается.
        </p>
      )}
      {invitation.status === 'accepted' && expanded && (
        <Conversation invitationId={invitation.id} side="candidate" onRead={markRead} />
      )}
      {open && (
        <>
          <p className="hint">
            Если примете, компания увидит ваше имя, контакты и профиль. Ожидаемую зарплату она не увидит.
          </p>
          <div className="actions">
            <button
              type="button"
              className="button button-small"
              disabled={busy}
              onClick={() => run(() => api.POST('/api/candidate/invitations/{invitation_id}/accept', params))}
            >
              Принять
            </button>
            <button
              type="button"
              className="button button-small button-secondary"
              disabled={busy}
              onClick={() => run(() => api.POST('/api/candidate/invitations/{invitation_id}/decline', params))}
            >
              Отклонить
            </button>
          </div>
        </>
      )}
      {error && <p className="error">{error}</p>}
    </details>
  )
}
