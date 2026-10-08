import { useCallback, useEffect, useState } from 'react'
import { api, errorMessage, type SentInvitations } from '../api/client'

/** Отправленные приглашения компании и бюджет недели; `reload` — после отправки нового. */
export function useSentInvitations() {
  const [sent, setSent] = useState<SentInvitations | null>(null)
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(() => {
    api.GET('/api/employer/invitations').then(({ data, error }) => {
      if (data) {
        setSent(data)
        setError(null)
      } else setError(errorMessage(error))
    })
  }, [])

  useEffect(reload, [reload])

  return { sent, error, reload }
}
