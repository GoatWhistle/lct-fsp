import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api, errorMessage, type Profile } from '../api/client'
import { workFormatWord } from '../employer/words'
import { rublesWords, yearsWords } from './words'

/** Профиль в кабинете: кратко, что заполнено, кто что видит, и стандартизированный PDF. */
export function ProfileCard() {
  const [profile, setProfile] = useState<Profile | null | undefined>(undefined)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.GET('/api/candidate/profile').then(({ data, error }) => {
      if (error) setError(errorMessage(error))
      else setProfile(data ?? null)
    })
  }, [])

  if (error) return <p className="error">{error}</p>
  if (profile === undefined) return null
  if (!profile) {
    return (
      <div className="card form">
        <h2>Профиль</h2>
        <p>
          Расскажите о себе: роли, стаж, стек и ожидания по формату и зарплате. Из профиля
          собирается PDF единого вида, а работодатель видит стек, роли и стаж в обезличенной
          карточке — без имени и контактов.
        </p>
        <div className="actions">
          <Link to="/candidate/profile" className="button">
            Заполнить профиль
          </Link>
        </div>
      </div>
    )
  }

  const formats = profile.work_formats.map((f) => workFormatWord(f).toLowerCase()).join(', ')
  const expectations = [
    formats.charAt(0).toUpperCase() + formats.slice(1),
    profile.city && `${profile.city}${profile.relocation ? ', готов к переезду' : ''}`,
  ].filter(Boolean)

  return (
    <div className="card profile-card">
      <div className="section-head">
        <div>
          <span className="muted">Ваш профиль</span>
          <h2 className="company-name">{profile.full_name}</h2>
        </div>
        <div className="actions">
          <PdfButton name={profile.full_name} />
          <Link to="/candidate/profile" className="button button-small button-secondary">
            Изменить
          </Link>
        </div>
      </div>
      <p>
        {profile.job_roles.length > 0 && `${profile.job_roles.join(' · ')} · `}
        стаж в ИТ — {yearsWords(profile.experience_years)}
      </p>
      <p className="muted">{expectations.join(' · ')}</p>
      {profile.stack.length > 0 && (
        <ul className="chips">
          {profile.stack.map((t) => (
            <li key={t.code} className="chip">
              {t.name}
            </li>
          ))}
        </ul>
      )}
      <p className="hint">
        До принятия приглашения работодатель видит категорию, профиль навыков, стек, роли, стаж и
        формат — без имени, контактов и «о себе». Ожидаемую зарплату — от{' '}
        {rublesWords(profile.salary_from)} — он не видит никогда.
      </p>
    </div>
  )
}

function PdfButton({ name }: { name: string }) {
  const [downloading, setDownloading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function download() {
    setDownloading(true)
    setError(null)
    const { data, error } = await api.GET('/api/candidate/profile/pdf', { parseAs: 'blob' })
    setDownloading(false)
    if (!data) {
      setError(errorMessage(error))
      return
    }
    const url = URL.createObjectURL(data)
    const link = document.createElement('a')
    link.href = url
    link.download = `Профиль кандидата — ${name}.pdf`
    document.body.append(link)
    link.click()
    link.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  return (
    <>
      {error && <span className="error">{error}</span>}
      <button type="button" className="button button-small" disabled={downloading} onClick={download}>
        {downloading ? 'Собираем PDF…' : 'Скачать PDF'}
      </button>
    </>
  )
}
