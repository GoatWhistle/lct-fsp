import type { ReactNode } from 'react'

/**
 * Кабинет роли: готовые разделы и список того, что появится со следующими задачами. `unread` —
 * непрочитанные сообщения во всех переписках; почты нет, счётчик — единственное уведомление.
 */
export function Cabinet({
  title,
  upcoming,
  unread = 0,
  children,
}: {
  title: string
  upcoming: string[]
  unread?: number
  children?: ReactNode
}) {
  return (
    <section className="stack">
      <div className="section-head">
        <h1>{title}</h1>
        {unread > 0 && <span className="tag">Новых сообщений: {unread}</span>}
      </div>
      {children}
      {upcoming.length > 0 && (
        <div className="card">
          <h2>Скоро здесь</h2>
          <ul className="upcoming">
            {upcoming.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}
