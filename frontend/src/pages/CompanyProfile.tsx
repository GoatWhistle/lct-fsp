import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { api, errorMessage, type CompanyInput, type Industry } from '../api/client'
import { useAuth } from '../auth/context'

/** Профиль компании: кто приглашает кандидата. Контакты увидит кандидат в приглашении. */
export function CompanyProfile() {
  const email = useAuth().user?.email ?? ''
  const navigate = useNavigate()
  const [industries, setIndustries] = useState<Industry[]>([])
  const [form, setForm] = useState<CompanyInput | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    Promise.all([api.GET('/api/employer/company'), api.GET('/api/catalog/industries')]).then(([company, catalog]) => {
      if (company.error || !catalog.data) {
        setError(errorMessage(company.error ?? catalog.error))
        return
      }
      const data = company.data
      setIndustries(catalog.data)
      setForm(
        data
          ? {
              name: data.name,
              industry: data.industry.code,
              description: data.description,
              website: data.website ?? '',
              contact_email: data.contact_email,
              contact_phone: data.contact_phone ?? '',
            }
          : {
              name: '',
              // Сфера выбирается явно: молча подставленная первая исказила бы профиль.
              industry: '',
              description: '',
              website: '',
              contact_email: email,
              contact_phone: '',
            },
      )
    })
  }, [email])

  if (!form) return error ? <p className="error">{error}</p> : <p className="muted">Загрузка…</p>

  function set<K extends keyof CompanyInput>(key: K, value: CompanyInput[K]) {
    setForm((current) => (current ? { ...current, [key]: value } : current))
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!form) return
    setSubmitting(true)
    setError(null)
    const { data, error } = await api.PUT('/api/employer/company', { body: form })
    setSubmitting(false)
    if (data) navigate('/employer')
    else setError(errorMessage(error))
  }

  return (
    <section className="stack">
      <h1>Профиль компании</h1>
      <form onSubmit={submit} className="card form">
        <label className="field">
          Название
          <input required maxLength={200} value={form.name} onChange={(e) => set('name', e.target.value)} />
        </label>
        <label className="field">
          Сфера деятельности
          <select value={form.industry} onChange={(e) => set('industry', e.target.value)} required>
            <option value="" disabled>
              Выберите сферу
            </option>
            {industries.map((i) => (
              <option key={i.code} value={i.code}>
                {i.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Описание
          <textarea
            required
            rows={5}
            maxLength={3000}
            value={form.description}
            onChange={(e) => set('description', e.target.value)}
          />
          <span className="hint">Чем занимается компания, продукт и команда — кандидат решает по этому тексту</span>
        </label>
        <div className="field-row">
          <label className="field">
            Email для связи
            <input
              type="email"
              required
              autoComplete="email"
              value={form.contact_email}
              onChange={(e) => set('contact_email', e.target.value)}
            />
          </label>
          <label className="field">
            Телефон
            <input
              type="tel"
              maxLength={32}
              autoComplete="tel"
              value={form.contact_phone ?? ''}
              onChange={(e) => set('contact_phone', e.target.value)}
            />
          </label>
        </div>
        <label className="field">
          Сайт
          <input
            inputMode="url"
            maxLength={300}
            placeholder="example.ru"
            value={form.website ?? ''}
            onChange={(e) => set('website', e.target.value)}
          />
        </label>
        {error && <p className="error">{error}</p>}
        <div className="actions">
          <button type="submit" className="button" disabled={submitting}>
            Сохранить
          </button>
          <Link to="/employer">Отмена</Link>
        </div>
      </form>
    </section>
  )
}
