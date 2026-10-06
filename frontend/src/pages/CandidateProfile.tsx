import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import {
  api,
  errorMessage,
  type Industry,
  type Profile,
  type ProfileInput,
  type Technology,
  type WorkFormat,
} from '../api/client'
import { useAuth } from '../auth/context'
import { SalaryInput } from '../components/SalaryInput'
import { TagInput } from '../components/TagInput'
import { TechnologyPicker } from '../components/TechnologyPicker'
import { workFormats } from '../employer/words'

const DISCLOSED = 'Работодатель увидит только после того, как вы примете его приглашение или откликнетесь сами'

type Draft = {
  full_name: string
  contact_email: string
  contact_phone: string
  telegram: string
  about: string
  stack: string[]
  job_roles: string[]
  experience_years: string
  soft_skills: string[]
  work_formats: WorkFormat[]
  city: string
  relocation: boolean
  industries: string[]
  salary_from: string
}

function emptyDraft(email: string): Draft {
  return {
    full_name: '',
    contact_email: email,
    contact_phone: '',
    telegram: '',
    about: '',
    stack: [],
    job_roles: [],
    experience_years: '',
    soft_skills: [],
    work_formats: [],
    city: '',
    relocation: false,
    industries: [],
    salary_from: '',
  }
}

function draftOf(profile: Profile): Draft {
  return {
    full_name: profile.full_name,
    contact_email: profile.contact_email,
    contact_phone: profile.contact_phone ?? '',
    telegram: profile.telegram ? `@${profile.telegram}` : '',
    about: profile.about,
    stack: profile.stack.map((t) => t.code),
    job_roles: profile.job_roles,
    experience_years: profile.experience_years.toString(),
    soft_skills: profile.soft_skills,
    work_formats: profile.work_formats,
    city: profile.city ?? '',
    relocation: profile.relocation,
    industries: profile.industries.map((i) => i.code),
    salary_from: profile.salary_from.toString(),
  }
}

function inputOf(draft: Draft): ProfileInput {
  return {
    ...draft,
    contact_phone: draft.contact_phone.trim() || null,
    telegram: draft.telegram.trim() || null,
    experience_years: Number(draft.experience_years),
    city: draft.city.trim() || null,
    salary_from: Number(draft.salary_from),
  }
}

/** Профиль кандидата: кто он, контакты, стек и ожидания. Категорию он не меняет — её определяет только тест. */
export function CandidateProfile() {
  const email = useAuth().user?.email ?? ''
  const navigate = useNavigate()
  const [technologies, setTechnologies] = useState<Technology[]>([])
  const [industries, setIndustries] = useState<Industry[]>([])
  const [draft, setDraft] = useState<Draft | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    Promise.all([
      api.GET('/api/candidate/profile'),
      api.GET('/api/catalog/technologies'),
      api.GET('/api/catalog/industries'),
    ]).then(([profile, catalog, spheres]) => {
      if (profile.error || !catalog.data || !spheres.data) {
        setError(errorMessage(profile.error ?? catalog.error ?? spheres.error))
        return
      }
      setTechnologies(catalog.data)
      setIndustries(spheres.data)
      setDraft(profile.data ? draftOf(profile.data) : emptyDraft(email))
    })
  }, [email])

  if (!draft) return error ? <p className="error">{error}</p> : <p className="muted">Загрузка…</p>

  function change(changes: Partial<Draft>) {
    setDraft((current) => (current ? { ...current, ...changes } : current))
  }

  function toggleFormat(format: WorkFormat) {
    if (!draft) return
    const chosen = draft.work_formats.includes(format)
      ? draft.work_formats.filter((f) => f !== format)
      : [...draft.work_formats, format]
    change({ work_formats: chosen })
  }

  function toggleIndustry(code: string) {
    if (!draft) return
    const chosen = draft.industries.includes(code)
      ? draft.industries.filter((c) => c !== code)
      : [...draft.industries, code]
    change({ industries: chosen })
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!draft) return
    if (draft.work_formats.length === 0) {
      setError('Выберите хотя бы один формат работы')
      return
    }
    setSubmitting(true)
    setError(null)
    const { data, error } = await api.PUT('/api/candidate/profile', { body: inputOf(draft) })
    setSubmitting(false)
    if (data) navigate('/candidate')
    else setError(errorMessage(error))
  }

  const onlyRemote = draft.work_formats.length === 1 && draft.work_formats[0] === 'remote'

  return (
    <section className="stack">
      <h1>Профиль</h1>
      <p className="lead">
        То, что вы рассказываете о себе сами. Категорию определяет только тест, а профиль помогает
        работодателю понять, кто вы, и собирается в PDF единого вида.
      </p>
      <form onSubmit={submit} className="card form">
        <h2>О себе</h2>
        <label className="field">
          ФИО
          <input
            required
            maxLength={200}
            autoComplete="name"
            value={draft.full_name}
            onChange={(e) => change({ full_name: e.target.value })}
          />
          <span className="hint">{DISCLOSED}</span>
        </label>
        <div className="field">
          Роли
          <TagInput
            label="Добавить роль"
            tags={draft.job_roles}
            onChange={(job_roles) => change({ job_roles })}
            max={10}
            maxLength={100}
            placeholder="Бэкенд-разработчик, тимлид — Enter добавляет"
          />
          <span className="hint">Кем работали или хотите работать. {DISCLOSED}</span>
        </div>
        <label className="field narrow-field">
          Стаж в ИТ, полных лет
          <input
            type="number"
            required
            min={0}
            max={60}
            step={1}
            inputMode="numeric"
            value={draft.experience_years}
            onChange={(e) => change({ experience_years: e.target.value })}
          />
          <span className="hint">0 — меньше года</span>
        </label>
        <div className="field">
          Софт-скиллы
          <TagInput
            label="Добавить софт-скилл"
            tags={draft.soft_skills}
            onChange={(soft_skills) => change({ soft_skills })}
            max={15}
            maxLength={50}
            placeholder="Наставничество, публичные выступления"
          />
          <span className="hint">{DISCLOSED}</span>
        </div>
        <label className="field">
          О себе
          <textarea
            rows={4}
            maxLength={3000}
            value={draft.about}
            onChange={(e) => change({ about: e.target.value })}
          />
          <span className="hint">{DISCLOSED}</span>
        </label>

        <h2>Контакты</h2>
        <p className="hint">
          Работодатель получит контакты, только когда вы примете его приглашение или откликнетесь
          сами. До этого он видит обезличенную карточку: категорию, профиль навыков, стек, стаж,
          формат работы и интересные сферы.
        </p>
        <div className="field-row">
          <label className="field">
            Email для связи
            <input
              type="email"
              required
              autoComplete="email"
              value={draft.contact_email}
              onChange={(e) => change({ contact_email: e.target.value })}
            />
          </label>
          <label className="field">
            Телефон
            <input
              type="tel"
              maxLength={32}
              autoComplete="tel"
              value={draft.contact_phone}
              onChange={(e) => change({ contact_phone: e.target.value })}
            />
          </label>
        </div>
        <label className="field">
          Telegram
          <input
            maxLength={64}
            placeholder="@username"
            pattern="(@|(https?://)?t\.me/)?[A-Za-z0-9_]{5,32}"
            title="Имя пользователя: от 5 до 32 латинских букв, цифр и _"
            value={draft.telegram}
            onChange={(e) => change({ telegram: e.target.value })}
          />
        </label>

        <h2>Стек</h2>
        <fieldset className="plain">
          <legend className="visually-hidden">Технологии стека</legend>
          <TechnologyPicker
            technologies={technologies}
            selected={draft.stack}
            onChange={(stack) => change({ stack })}
          />
          <span className="hint">
            Из справочника технологий. В подборке стек весит немного: уровень по темам определяет
            тест.
          </span>
        </fieldset>

        <h2>Ожидания</h2>
        <fieldset className="plain">
          <legend>Формат работы</legend>
          <div className="chips">
            {workFormats.map((f) => (
              <button
                key={f.value}
                type="button"
                className={draft.work_formats.includes(f.value) ? 'chip chip-toggle selected' : 'chip chip-toggle'}
                aria-pressed={draft.work_formats.includes(f.value)}
                onClick={() => toggleFormat(f.value)}
              >
                {f.title}
              </button>
            ))}
          </div>
          <span className="hint">Отметьте все подходящие</span>
        </fieldset>
        <div className="field-row">
          <label className="field">
            Город
            <input
              required={!onlyRemote}
              maxLength={100}
              autoComplete="address-level2"
              value={draft.city}
              onChange={(e) => change({ city: e.target.value })}
            />
            <span className="hint">{onlyRemote ? 'Для удалённой работы — по желанию' : 'Где вы живёте'}</span>
          </label>
          <SalaryInput
            label="Зарплата от"
            value={draft.salary_from}
            onChange={(salary_from) => change({ salary_from })}
            hint="Работодатель её не видит: по ней система оценивает, подойдёт ли вам его вилка"
          />
        </div>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={draft.relocation}
            onChange={(e) => change({ relocation: e.target.checked })}
          />
          Готов к переезду
        </label>
        <fieldset className="plain">
          <legend>Интересные сферы бизнеса</legend>
          <div className="chips">
            {industries.map((i) => (
              <button
                key={i.code}
                type="button"
                className={draft.industries.includes(i.code) ? 'chip chip-toggle selected' : 'chip chip-toggle'}
                aria-pressed={draft.industries.includes(i.code)}
                onClick={() => toggleIndustry(i.code)}
              >
                {i.name}
              </button>
            ))}
          </div>
          <span className="hint">
            По желанию. На категорию не влияет — помогает понять, какие приглашения вам интереснее
          </span>
        </fieldset>

        {error && <p className="error">{error}</p>}
        <div className="actions">
          <button type="submit" className="button" disabled={submitting}>
            Сохранить
          </button>
          <Link to="/candidate">Отмена</Link>
        </div>
      </form>
    </section>
  )
}
