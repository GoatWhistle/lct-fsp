import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { api, errorMessage, type Message, type Side } from '../api/client'
import { dateTimeWords } from '../candidate/words'

/**
 * Переписка внутри принятого приглашения — только текст, старые сверху. Открытие отмечает
 * сообщения другой стороны прочитанными; `onRead` — обновить счётчики непрочитанного.
 */
export function Conversation({
  invitationId,
  side,
  onRead,
}: {
  invitationId: string
  side: Side
  onRead?: () => void
}) {
  const [messages, setMessages] = useState<Message[] | null>(null)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const params = { params: { path: { invitation_id: invitationId } } }

  const load = useCallback(() => {
    const path = { params: { path: { invitation_id: invitationId } } }
    const request =
      side === 'candidate'
        ? api.GET('/api/candidate/invitations/{invitation_id}/messages', path)
        : api.GET('/api/employer/invitations/{invitation_id}/messages', path)
    request.then(({ data, error }) => {
      if (data) {
        setMessages(data)
        onRead?.()
      } else setError(errorMessage(error))
    })
  }, [invitationId, side, onRead])

  useEffect(load, [load])

  async function send(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    const body = { ...params, body: { text } }
    const { data, error } =
      side === 'candidate'
        ? await api.POST('/api/candidate/invitations/{invitation_id}/messages', body)
        : await api.POST('/api/employer/invitations/{invitation_id}/messages', body)
    setBusy(false)
    if (data) {
      setMessages((current) => [...(current ?? []), data])
      setText('')
    } else setError(errorMessage(error))
  }

  const other = side === 'candidate' ? 'Компания' : 'Кандидат'
  return (
    <div className="conversation">
      <div className="section-head">
        <h3>Переписка</h3>
        <button type="button" className="button button-small button-secondary" onClick={load}>
          Обновить
        </button>
      </div>
      {messages && messages.length === 0 && (
        <p className="muted">Сообщений пока нет. Новые видны в кабинете счётчиком, на почту они не приходят.</p>
      )}
      {messages && messages.length > 0 && (
        <ol className="messages">
          {messages.map((m) => (
            <li key={m.id} className={m.author === side ? 'message mine' : 'message'}>
              <span className="muted">
                {m.author === side ? 'Вы' : other} · {dateTimeWords(m.sent_at)}
              </span>
              <p className="prewrap">{m.text}</p>
            </li>
          ))}
        </ol>
      )}
      <form className="field" onSubmit={send}>
        <textarea
          rows={3}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Сообщение"
          aria-label="Сообщение"
        />
        <div className="actions">
          <button type="submit" className="button button-small" disabled={busy || text.trim() === ''}>
            Отправить
          </button>
        </div>
      </form>
      {error && <p className="error">{error}</p>}
    </div>
  )
}
