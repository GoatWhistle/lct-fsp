import type { ExperienceEntry, TechnologyYears } from '../api/client'
import { periodWords, technologyYearsWords } from '../candidate/words'

/**
 * Карточка опыта со слов кандидата — отдельно от подтверждённого тестом и ФСП. Годы по
 * технологиям посчитаны бэкендом из записей. На скор, место в выдаче, уровень и категорию не
 * влияет.
 */
export function ExperienceCard({
  experience,
  technologyYears,
}: {
  experience: ExperienceEntry[]
  technologyYears: TechnologyYears[]
}) {
  if (experience.length === 0) return null
  return (
    <div className="experience-card">
      <h3>
        Опыт <span className="muted">— со слов кандидата</span>
      </h3>
      <ul className="experience-list">
        {experience.map((e, i) => (
          <li key={i}>
            <span className="muted">{periodWords(e.start, e.end)}</span>
            <div>
              <strong>{[e.role, e.place].filter(Boolean).join(' · ')}</strong>
            </div>
            {e.stack.length > 0 && <div className="muted">{e.stack.map((t) => t.name).join(', ')}</div>}
            {e.summary && <p className="prewrap">{e.summary}</p>}
          </li>
        ))}
      </ul>
      {technologyYears.length > 0 && (
        <p>
          Годы по технологиям:{' '}
          {technologyYears.map((y) => `${y.technology.name} — ${technologyYearsWords(y.years)}`).join(', ')}
        </p>
      )}
      <p className="hint">
        Тестом и ФСП не подтверждено: на подбор, уровень и категорию не влияет. Годы считаются из
        периодов записей без двойного счёта пересечений, вниз до полугода.
      </p>
    </div>
  )
}
