import { useCallback, useEffect, useState } from 'react'
import { api, type Role } from '../api/client'

/** Непрочитанные сообщения роли во всех переписках — из кабинета; `reload` — после открытия
 * переписки. Не загрузилось — счётчик просто не показывается. */
export function useUnreadMessages(role: Role) {
  const [unread, setUnread] = useState(0)

  const reload = useCallback(() => {
    const request = role === 'candidate' ? api.GET('/api/candidate/cabinet') : api.GET('/api/employer/cabinet')
    request.then(({ data }) => {
      if (data) setUnread(data.unread_messages)
    })
  }, [role])

  useEffect(reload, [reload])

  return { unread, reload }
}
