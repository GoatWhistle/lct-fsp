import type { SkillProfile, TestResult } from '../api/client'
import { gradeName, type Catalog } from './catalog'
import { levelWords, percent, thetaWithError } from './words'

/** Оценка теста: общий уровень словами и вероятность каждого грейда — по ней решается категория. */
export function TestResultView({ catalog, result }: { catalog: Catalog; result: TestResult }) {
  return (
    <div className="card">
      <h2>Результат теста</h2>
      <p className="level">
        Уровень — <strong>{levelWords(result.overall.band)}</strong>{' '}
        <span className="muted">({thetaWithError(result.overall)})</span>
      </p>
      <table className="table">
        <caption className="hint">Вероятность, что ваш общий уровень не ниже порога грейда</caption>
        <tbody>
          {result.grade_probabilities.map((p) => (
            <tr key={p.grade}>
              <th scope="row">{gradeName(catalog, p.grade)}</th>
              <td className="bar-cell">
                <span className="bar" style={{ width: `${Math.round(p.probability * 100)}%` }} />
              </td>
              <td className="num">{percent(p.probability)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="hint">
        Грейд присваивается, только когда эта вероятность высока: так система почти не завышает
        категорию. Уровень — на шкале теста, ± — погрешность.
      </p>
    </div>
  )
}

/** Профиль навыков по темам — его видит подбор работодателя. */
export function SkillProfileView({ profile }: { profile: SkillProfile }) {
  return (
    <div className="card">
      <h2>Профиль навыков</h2>
      <p className="muted">
        Собран из всех ваших тестов. Работодатель видит его в обезличенной карточке.
      </p>
      <table className="table">
        <tbody>
          {profile.topics.map((t) => (
            <tr key={t.topic.code}>
              <th scope="row">{t.topic.name}</th>
              <td>{levelWords(t.level.band)}</td>
              <td className="num muted">{thetaWithError(t.level)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
