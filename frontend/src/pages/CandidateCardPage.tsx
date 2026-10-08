import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { api, errorMessage, type CandidateCard } from '../api/client'
import { CandidateCardView } from '../employer/CandidateCardView'
import { InviteAction } from '../employer/Invite'
import { useSentInvitations } from '../employer/invitations'
import { latestByCandidate } from '../invitation/words'

/** Карточка кандидата для работодателя: приглашение отсюда и раскрытый профиль после принятия. */
export function CandidateCardPage() {
  const { id } = useParams()
  const [loaded, setLoaded] = useState<{ id: string; card: CandidateCard | null; error: string | null } | null>(
    null,
  )
  const { sent, error: invitationsError, reload } = useSentInvitations()

  useEffect(() => {
    if (!id) return
    let stale = false
    api
      .GET('/api/employer/candidates/{candidate_id}', { params: { path: { candidate_id: id } } })
      .then(({ data, error }) => {
        if (!stale) setLoaded({ id, card: data ?? null, error: data ? null : errorMessage(error) })
      })
    return () => {
      stale = true
    }
  }, [id])

  const current = loaded?.id === id ? loaded : null
  if (current?.error) return <p className="error">{current.error}</p>
  if (!id || !current?.card) return <p className="muted">Загрузка…</p>

  return (
    <section className="stack">
      <div>
        <Link to="/employer">← Кабинет</Link>
      </div>
      <h1>Карточка кандидата</h1>
      <div className="card">
        <CandidateCardView card={current.card} />
      </div>
      <div className="card">
        {invitationsError ? (
          <p className="error">Приглашения не загрузились: {invitationsError}</p>
        ) : (
          sent && (
            <InviteAction
              candidateId={id}
              latest={latestByCandidate(sent.invitations).get(id)}
              budget={sent.budget}
              onSent={reload}
            />
          )
        )}
      </div>
    </section>
  )
}
