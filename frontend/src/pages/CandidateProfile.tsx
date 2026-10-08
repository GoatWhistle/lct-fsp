import { useEffect, useState, type ChangeEvent, type FormEvent, type ReactNode } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import {
  api,
  errorMessage,
  type HideableField,
  type Industry,
  type Profile,
  type ProfileInput,
  type ResumeDraft,
  type ResumeField,
  type Technology,
  type WorkFormat,
} from '../api/client'
import { useAuth } from '../auth/context'
import { fspReturnError } from '../candidate/fsp'
import { FspCard } from '../candidate/FspCard'
import { SalaryInput } from '../components/SalaryInput'
import { TagInput } from '../components/TagInput'
import { TechnologyPicker } from '../components/TechnologyPicker'
import { hideableWords } from '../candidate/words'
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
  hidden: HideableField[]
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
    hidden: [],
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
    hidden: profile.hidden,
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
    // Пустой город скрывать нечего: «скрыто» не путается с «не заполнено».
    hidden: draft.city.trim() ? draft.hidden : draft.hidden.filter((f) => f !== 'city'),
  }
}

/** Что из черновика резюме ложится в форму: распознанное заменяет поле, остальное остаётся как было. */
function withResume(draft: Draft, parsed: ResumeDraft): Draft {
  return {
    ...draft,
    full_name: parsed.full_name ?? draft.full_name,
    contact_email: parsed.contact_email ?? draft.contact_email,
    contact_phone: parsed.contact_phone ?? draft.contact_phone,
    telegram: parsed.telegram ? `@${parsed.telegram}` : draft.telegram,
    stack: parsed.stack.length ? parsed.stack.map((t) => t.code) : draft.stack,
    job_roles: parsed.job_roles.length ? parsed.job_roles : draft.job_roles,
    experience_years: parsed.experience_years?.toString() ?? draft.experience_years,
    soft_skills: parsed.soft_skills.length ? parsed.soft_skills : draft.soft_skills,
  }
}

type ResumeMarks = { filled: ResumeField[]; uncertain: ResumeField[]; hint: ResumeDraft['grade_hint'] }

/** Профиль кандидата: кто он, контакты, стек и ожидания. Категорию он не меняет — её определяет только тест. */
export function CandidateProfile() {
  const email = useAuth().user?.email ?? ''
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [technologies, setTechnologies] = useState<Technology[]>([])
  const [industries, setIndustries] = useState<Industry[]>([])
  const [draft, setDraft] = useState<Draft | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [resume, setResume] = useState<ResumeMarks | null>(null)
  const [resumeError, setResumeError] = useState<string | null>(null)
  const [parsing, setParsing] = useState(false)

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
    // Поле, которое кандидат поправил, больше не подсвечивается.
    setResume((current) =>
      current
        ? { ...current, uncertain: current.uncertain.filter((f) => !(f in changes)) }
        : current,
    )
  }

  async function parseResume(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    setParsing(true)
    setResumeError(null)
    const { data, error } = await api.POST('/api/candidate/profile/resume', {
      // Тело — сам файл как есть: его отдаёт bodySerializer.
      body: '',
      bodySerializer: () => file,
      headers: { 'Content-Type': 'application/pdf' },
    })
    setParsing(false)
    if (!data) {
      setResumeError(errorMessage(error))
      return
    }
    setDraft((current) => (current ? withResume(current, data) : current))
    setResume({
      filled: Object.keys(data.confidence) as ResumeField[],
      uncertain: data.uncertain,
      hint: data.grade_hint,
    })
  }

  function mark(field: ResumeField): ReactNode {
    return resume?.uncertain.includes(field) ? (
      <span className="draft-mark">Проверьте: система не уверена</span>
    ) : null
  }

  function flagClass(field: ResumeField, base: string): string {
    return resume?.uncertain.includes(field) ? `${base} flagged` : base
  }

  function toggleFormat(format: WorkFormat) {
    if (!draft) return
    const chosen = draft.work_formats.includes(format)
      ? draft.work_formats.filter((f) => f !== format)
      : [...draft.work_formats, format]
    change({ work_formats: chosen })
  }

  function toggleVisible(field: HideableField, visible: boolean) {
    if (!draft) return
    change({ hidden: visible ? draft.hidden.filter((f) => f !== field) : [...draft.hidden, field] })
  }

  function visibility(field: HideableField) {
    return (
      <VisibilityToggle
        what={hideableWords[field]}
        visible={!draft?.hidden.includes(field)}
        onChange={(visible) => toggleVisible(field, visible)}
      />
    )
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
      <FspCard
        notice={params.get('fsp') === 'linked' ? 'ФСП ID привязан, достижения добавлены в профиль' : null}
        returnError={fspReturnError(params.get('fsp_error'))}
      />
      <div className="card form">
        <h2>Заполнить по резюме</h2>
        <label className="field">
          PDF резюме
          <input type="file" accept="application/pdf,.pdf" disabled={parsing} onChange={parseResume} />
          <span className="hint">
            PDF с текстом до 5 МБ и 10 страниц. Разбор идёт на сервере платформы, файл никуда не
            отправляется и не сохраняется. Текст, которого не видно на странице, система не читает.
          </span>
        </label>
        {parsing && <p className="muted">Разбираем…</p>}
        {resumeError && <p className="error">{resumeError}</p>}
        {resume && (
          <div className="stack">
            <p>
              <strong>Система поняла так.</strong>{' '}
              {resume.filled.length
                ? 'Распознанное подставлено в форму ниже, выделенное проверьте. Ничего не сохранено, пока вы не нажмёте «Сохранить».'
                : 'В резюме не нашлось полей профиля — заполните форму вручную.'}
            </p>
            <p className="hint">
              Резюме — ваше самоописание: в подборке весит только стек и немного. Категорию определяет
              только тест.
            </p>
            {resume.hint && (
              <p className="hint">
                По стажу и ролям подходит грейд {resume.hint.grade.name}. Это подсказка для шага выбора
                грейда — выбираете вы, проверяет тест.
              </p>
            )}
          </div>
        )}
      </div>
      <form onSubmit={submit} className="card form">
        <h2>О себе</h2>
        <label className={flagClass('full_name', 'field')}>
          <span>ФИО {mark('full_name')}</span>
          <input
            required
            maxLength={200}
            autoComplete="name"
            value={draft.full_name}
            onChange={(e) => change({ full_name: e.target.value })}
          />
          <span className="hint">{DISCLOSED}</span>
        </label>
        <div className={flagClass('job_roles', 'field')}>
          <span>Роли {mark('job_roles')}</span>
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
        <label className={flagClass('experience_years', 'field narrow-field')}>
          <span>Стаж в ИТ, полных лет {mark('experience_years')}</span>
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
        {visibility('experience_years')}
        <div className={flagClass('soft_skills', 'field')}>
          <span>Софт-скиллы {mark('soft_skills')}</span>
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
          сами. До этого он видит обезличенную карточку: категорию, профиль навыков, формат работы
          и то из стека, стажа, города, переезда и интересных сфер, что вы оставили видимым.
          Скрытое не влияет на подбор и всегда есть в вашем PDF-профиле.
        </p>
        <div className="field-row">
          <label className={flagClass('contact_email', 'field')}>
            <span>Email для связи {mark('contact_email')}</span>
            <input
              type="email"
              required
              autoComplete="email"
              value={draft.contact_email}
              onChange={(e) => change({ contact_email: e.target.value })}
            />
          </label>
          <label className={flagClass('contact_phone', 'field')}>
            <span>Телефон {mark('contact_phone')}</span>
            <input
              type="tel"
              maxLength={32}
              autoComplete="tel"
              value={draft.contact_phone}
              onChange={(e) => change({ contact_phone: e.target.value })}
            />
          </label>
        </div>
        <label className={flagClass('telegram', 'field')}>
          <span>Telegram {mark('telegram')}</span>
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
        <fieldset className={flagClass('stack', 'plain')}>
          <legend className="visually-hidden">Технологии стека</legend>
          {mark('stack')}
          <TechnologyPicker
            technologies={technologies}
            selected={draft.stack}
            onChange={(stack) => change({ stack })}
          />
          <span className="hint">
            Из справочника технологий. В подборке стек весит немного: уровень по темам определяет
            тест.
          </span>
          {visibility('stack')}
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
        {draft.city.trim() && visibility('city')}
        <label className="checkbox">
          <input
            type="checkbox"
            checked={draft.relocation}
            onChange={(e) => change({ relocation: e.target.checked })}
          />
          Готов к переезду
        </label>
        {visibility('relocation')}
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
          {visibility('industries')}
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

/** Переключатель «видно работодателю»: до раскрытия скрытое поле в карточке не показывается. */
function VisibilityToggle({
  what,
  visible,
  onChange,
}: {
  what: string
  visible: boolean
  onChange: (visible: boolean) => void
}) {
  return (
    <label className="checkbox visibility">
      <input type="checkbox" checked={visible} onChange={(e) => onChange(e.target.checked)} />
      {what.charAt(0).toUpperCase() + what.slice(1)} — видно работодателю до раскрытия
    </label>
  )
}
