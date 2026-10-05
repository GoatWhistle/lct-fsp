/** Пустой кабинет роли: разделы появятся со следующими задачами. */
export function Cabinet({ title, upcoming }: { title: string; upcoming: string[] }) {
  return (
    <section>
      <h1>{title}</h1>
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
