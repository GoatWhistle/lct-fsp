import type { CandidateCard } from '../api/client'
import { fspResultWords } from '../candidate/fsp'
import { hideableWords, levelWords, thetaWithError, yearsWords } from '../candidate/words'
import { gradeStatusWords, workFormatWord } from './words'

/**
 * Карточка кандидата для работодателя как её отдал бэкенд: обезличенная до принятия приглашения,
 * с именем, контактами и свободным текстом — после. Ожидаемой зарплаты в ней нет никогда.
 */
export function CandidateCardView({ card }: { card: CandidateCard }) {
  const self = card.self_reported
  const disclosed = card.disclosed
  return (
    <div className="stack card-details">
      {disclosed && (
        <div className="disclosed">
          <h3>{disclosed.full_name}</h3>
          <p>
            <a href={`mailto:${disclosed.contact_email}`}>{disclosed.contact_email}</a>
            {disclosed.contact_phone && ` · ${disclosed.contact_phone}`}
            {disclosed.telegram && (
              <>
                {' · '}
                <a href={`https://t.me/${disclosed.telegram}`} target="_blank" rel="noreferrer">
                  @{disclosed.telegram}
                </a>
              </>
            )}
          </p>
          {disclosed.job_roles.length > 0 && <p className="muted">{disclosed.job_roles.join(', ')}</p>}
          {disclosed.about && <p className="prewrap">{disclosed.about}</p>}
          {disclosed.soft_skills.length > 0 && (
            <ul className="chips">
              {disclosed.soft_skills.map((s) => (
                <li key={s} className="chip">
                  {s}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      <p className="muted">
        {card.category
          ? `Категория ${card.category.specialization.name} · ${card.category.grade.name} · `
          : 'Категории нет — '}
        {card.grade_status
          ? `грейд ${gradeStatusWords(card.grade_status)}`
          : 'кандидат откликнулся на вашу вакансию, тест не проходил'}
        {card.category?.verified_at && ' · уровень подтверждён проверочным блоком'}
      </p>
      {card.skill_profile && (
        <p>
          Общий уровень — <strong>{levelWords(card.skill_profile.overall.band)}</strong>{' '}
          <span className="muted">({thetaWithError(card.skill_profile.overall)})</span>
        </p>
      )}
      {self ? (
        <>
          <p className="muted">
            {[
              self.experience_years !== null && `Стаж в ИТ — ${yearsWords(self.experience_years)}`,
              self.work_formats.map((f) => workFormatWord(f).toLowerCase()).join(', '),
              self.city,
              self.relocation && 'готов к переезду',
              self.industries &&
                self.industries.length > 0 &&
                `интересные сферы: ${self.industries.map((i) => i.name).join(', ')}`,
            ]
              .filter(Boolean)
              .join(' · ')}
          </p>
          {self.stack && self.stack.length > 0 && (
            <ul className="chips">
              {self.stack.map((t) => (
                <li key={t.code} className="chip">
                  {t.name}
                </li>
              ))}
            </ul>
          )}
          {self.hidden.length > 0 && (
            <p className="hint">
              Скрыто кандидатом до принятия приглашения: {self.hidden.map((f) => hideableWords[f]).join(', ')}.
            </p>
          )}
        </>
      ) : (
        <p className="muted">Профиль кандидат ещё не заполнил — есть только категория и профиль навыков.</p>
      )}
      <FspAchievements card={card} />
      {!disclosed && (
        <p className="hint">Имя и контакты откроются, когда кандидат примет приглашение вашей компании.</p>
      )}
    </div>
  )
}

/** Достижения ФСП — подтверждены, отдельно от самоописания: до принятия приглашения — тип
 * результата, дисциплина и год, после — с мероприятием, местом и ролью в команде. */
function FspAchievements({ card }: { card: CandidateCard }) {
  if (card.fsp_details) {
    if (card.fsp_details.length === 0) return <p className="muted">Нет истории ФСП — профиль построен по тесту.</p>
    return (
      <div>
        <p>Подтверждено ФСП:</p>
        <ul className="upcoming">
          {card.fsp_details.map((a, i) => (
            <li key={i}>
              {a.date.slice(0, 4)} · {a.event} · {a.discipline.name} — {fspResultWords[a.result]}
              {a.place !== null && `, ${a.place} место`}
              {a.team_role && `, в команде — ${a.team_role.name}`}
            </li>
          ))}
        </ul>
      </div>
    )
  }
  if (card.fsp_achievements.length === 0) {
    return <p className="muted">Нет истории ФСП — профиль построен по тесту.</p>
  }
  return (
    <p>
      Подтверждено ФСП:{' '}
      {card.fsp_achievements.map((a) => `${fspResultWords[a.result]} — ${a.discipline.name}, ${a.year}`).join('; ')}
    </p>
  )
}
