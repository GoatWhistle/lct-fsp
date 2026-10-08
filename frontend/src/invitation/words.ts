import type { Invitation, InvitationStatus } from '../api/client'

/** Статус приглашения словами — для работодателя и кандидата одинаково. */
export const invitationStatusWords: Record<InvitationStatus, string> = {
  sent: 'отправлено',
  viewed: 'просмотрено',
  accepted: 'принято',
  declined: 'отклонено',
  expired: 'истекло без ответа',
}

/** Ждёт ответа кандидата: отправлено или просмотрено и не истекло — статус уже на момент ответа API. */
export function isOpen(invitation: Pick<Invitation, 'status'>): boolean {
  return invitation.status === 'sent' || invitation.status === 'viewed'
}

/** Последнее приглашение компании каждому кандидату; список с бэкенда — новые сверху. */
export function latestByCandidate(invitations: Invitation[]): Map<string, Invitation> {
  const latest = new Map<string, Invitation>()
  for (const invitation of invitations) {
    if (!latest.has(invitation.candidate_id)) latest.set(invitation.candidate_id, invitation)
  }
  return latest
}
