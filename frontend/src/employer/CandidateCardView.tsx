import type { CandidateCard } from '../api/client'
import { levelWords, thetaWithError, yearsWords } from '../candidate/words'
import { workFormatWord } from './words'

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
        Категория {card.category.specialization.name} · {card.category.grade.name}
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
            Стаж в ИТ — {yearsWords(self.experience_years)} ·{' '}
            {self.work_formats.map((f) => workFormatWord(f).toLowerCase()).join(', ')}
            {self.city && ` · ${self.city}${self.relocation ? ', готов к переезду' : ''}`}
            {self.industries.length > 0 && ` · интересные сферы: ${self.industries.map((i) => i.name).join(', ')}`}
          </p>
          {self.stack.length > 0 && (
            <ul className="chips">
              {self.stack.map((t) => (
                <li key={t.code} className="chip">
                  {t.name}
                </li>
              ))}
            </ul>
          )}
        </>
      ) : (
        <p className="muted">Профиль кандидат ещё не заполнил — есть только категория и профиль навыков.</p>
      )}
      {!disclosed && (
        <p className="hint">Имя и контакты откроются, когда кандидат примет приглашение вашей компании.</p>
      )}
    </div>
  )
}
