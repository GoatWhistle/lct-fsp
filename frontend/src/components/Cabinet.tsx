import type { ReactNode } from 'react'

/** Кабинет роли: готовые разделы и список того, что появится со следующими задачами. */
export function Cabinet({
  title,
  upcoming,
  children,
}: {
  title: string
  upcoming: string[]
  children?: ReactNode
}) {
  return (
    <section className="stack">
      <h1>{title}</h1>
      {children}
      <div className="card">
        <h2>Скоро здесь</h2>
        <ul className="upcoming">
          {upcoming.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>
    </section>
  )
}
