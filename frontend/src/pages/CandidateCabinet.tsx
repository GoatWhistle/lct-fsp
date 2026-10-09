import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api, errorMessage, type CandidatePath } from '../api/client'
import { Cabinet } from '../components/Cabinet'
import { gradeName, useCatalog, type Catalog } from '../candidate/catalog'
import { FeedbackCard } from '../candidate/FeedbackCard'
import { GradeChangeCard, HistoryView } from '../candidate/GradeChange'
import { GradeStep } from '../candidate/GradeStep'
import { Inbox } from '../candidate/Inbox'
import { ProfileCard } from '../candidate/ProfileCard'
import { SkillProfileView, TestResultView } from '../candidate/Results'
import { SurveyStep } from '../candidate/SurveyStep'
import { TestStep } from '../candidate/TestStep'
import { VerificationCard } from '../candidate/Verification'
import { FocusConsent } from '../candidate/protection'
import { dateWords, levelWords } from '../candidate/words'
import { useUnreadMessages } from '../invitation/unread'

const steps = ['Опрос', 'Грейд', 'Тест', 'Категория']
const stepOf: Record<CandidatePath['stage'], number> = {
  survey: 0,
  grade: 1,
  test: 2,
  offer: 2,
  verification: 2,
  no_category: 3,
  category: 3,
}

/** Без категории кабинет — это путь к ней: опрос → грейд → тест. Пропустить его нельзя. */
export function CandidateCabinet() {
  const { catalog, failed } = useCatalog()
  const [path, setPath] = useState<CandidatePath | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.GET('/api/candidate/path').then(({ data, error }) => {
      if (data) setPath(data)
      else setError(errorMessage(error))
    })
  }, [])

  if (error || failed) return <p className="error">{error ?? 'Не удалось загрузить справочники'}</p>
  if (!path || !catalog) return <p className="muted">Загрузка…</p>
  // Проверочный блок идёт на время: только его задания.
  if (path.verification?.progress) {
    return <VerificationCard catalog={catalog} path={path} onChange={setPath} />
  }
  // Блок по теме идёт при категории: только задания, профиль обновится по итогу.
  if (path.topic_block) {
    return (
      <section className="stack">
        <h1>Блок по теме «{path.topic_block.topic.name}»</h1>
        <p className="lead">
          {path.topic_block.items} заданий по одной теме: ответы уточнят уровень и погрешность в
          профиле навыков. Категория и грейд от блока не меняются.
        </p>
        <TestStep onDone={setPath} />
      </section>
    )
  }
  if (path.stage === 'category') return <CategoryCabinet catalog={catalog} path={path} onChange={setPath} />
  // Попытка вверх идёт при категории: только тест, категория до итога прежняя.
  if (path.stage === 'test' && path.category) {
    return (
      <section className="stack">
        <h1>Попытка на {gradeName(catalog, path.attempt?.grade ?? '')}</h1>
        <p className="lead">
          Ваша категория — {path.category.specialization.name} · {path.category.grade.name}. Она
          сменится, только если новый грейд подтвердится.
        </p>
        <TestStep onDone={setPath} />
      </section>
    )
  }

  return (
    <section className="stack">
      <h1>Путь к категории</h1>
      <p className="lead">
        Категория — ваша специализация и грейд, подтверждённые тестом. Работодатели подбирают
        кандидатов по категориям, поэтому без неё вас не видно в подборках.
      </p>
      <ol className="steps">
        {steps.map((step, i) => (
          <li key={step} className={i === stepOf[path.stage] ? 'current' : i < stepOf[path.stage] ? 'done' : ''}>
            {step}
          </li>
        ))}
      </ol>
      <PathStep catalog={catalog} path={path} onChange={setPath} />
      {/* Во время теста — только тест; профиль заполняется до или после. */}
      {path.stage !== 'test' && <ProfileCard />}
    </section>
  )
}

type StepProps = { catalog: Catalog; path: CandidatePath; onChange: (path: CandidatePath) => void }

function PathStep({ catalog, path, onChange }: StepProps) {
  const [editingSurvey, setEditingSurvey] = useState(false)

  function done(next: CandidatePath) {
    setEditingSurvey(false)
    onChange(next)
  }

  switch (path.stage) {
    case 'survey':
      return <SurveyStep catalog={catalog} current={null} onDone={done} />
    case 'grade':
      if (editingSurvey || !path.survey) {
        return (
          <SurveyStep
            catalog={catalog}
            current={path.survey}
            onDone={done}
            onCancel={path.survey ? () => setEditingSurvey(false) : undefined}
          />
        )
      }
      return (
        <GradeStep
          catalog={catalog}
          survey={path.survey}
          onDone={done}
          onChangeSurvey={() => setEditingSurvey(true)}
        />
      )
    case 'test':
      return <TestStep onDone={done} />
    case 'offer':
      return <OfferStep catalog={catalog} path={path} onChange={done} />
    case 'verification':
      return (
        <>
          <VerificationCard catalog={catalog} path={path} onChange={done} />
          <LowerGradeStep catalog={catalog} path={path} onChange={done} />
          {path.result && <TestResultView catalog={catalog} result={path.result} />}
        </>
      )
    case 'no_category':
      return (
        <>
          <div className="card">
            <h2>Категория пока не присвоена</h2>
            <p>
              Уверенности не хватило и для грейда «{gradeName(catalog, 'intern')}». Повторить тест
              можно с {path.retest_after ? dateWords(path.retest_after) : 'даты повтора'}. До тех
              пор стоит подтянуть темы, где уровень ниже.
            </p>
          </div>
          {path.result && <TestResultView catalog={catalog} result={path.result} />}
          {path.profile && <SkillProfileView profile={path.profile} />}
        </>
      )
    case 'category':
      return null
  }
}

/** Провал заявленного грейда: сразу дотест на грейд ниже, отказаться нельзя — путь обязательный. */
function OfferStep({ catalog, path, onChange }: StepProps) {
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [consent, setConsent] = useState(false)
  const offer = path.offer_grade ?? ''
  const tried = path.result?.grade ?? ''

  async function proceed() {
    setSubmitting(true)
    setError(null)
    const { data, error } = await api.POST('/api/candidate/path/attempts', {
      body: { grade: offer, focus_consent: consent },
    })
    setSubmitting(false)
    if (data) onChange(data)
    else setError(errorMessage(error))
  }

  return (
    <>
      <div className="card form">
        <h2>Уверенности для {gradeName(catalog, tried)} не хватило</h2>
        <p>
          Продолжите на {gradeName(catalog, offer)}: прошлые ответы засчитаются, добавим несколько
          заданий проще. Если хватит и их, сразу получите категорию.
        </p>
        <FocusConsent checked={consent} onChange={setConsent} />
        {error && <p className="error">{error}</p>}
        <div className="actions">
          <button type="button" className="button" disabled={submitting} onClick={proceed}>
            Продолжить на {gradeName(catalog, offer)}
          </button>
        </div>
      </div>
      {path.result && <TestResultView catalog={catalog} result={path.result} />}
    </>
  )
}

/**
 * Результат ждёт проверочного блока, а пройти его сейчас не хочется или блок разошёлся с тестом:
 * можно начать тест на грейд ниже с чистого листа — его результат снова проверяется по общему
 * правилу.
 */
function LowerGradeStep({ catalog, path, onChange }: StepProps) {
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [consent, setConsent] = useState(false)
  const pending = path.verification?.grade ?? ''
  const index = catalog.grades.findIndex((g) => g.code === pending)
  const lower = index > 0 ? catalog.grades[index - 1] : null
  if (!lower) return null

  async function start() {
    if (!lower) return
    setSubmitting(true)
    setError(null)
    const { data, error } = await api.POST('/api/candidate/path/attempts', {
      body: { grade: lower.code, focus_consent: consent },
    })
    setSubmitting(false)
    if (data) onChange(data)
    else setError(errorMessage(error))
  }

  return (
    <div className="card form">
      <p>Или начните тест на {lower.name} — новое измерение с чистого листа.</p>
      <FocusConsent checked={consent} onChange={setConsent} />
      {error && <p className="error">{error}</p>}
      <div className="actions">
        <button type="button" className="button button-secondary" disabled={submitting} onClick={start}>
          Тест на {lower.name}
        </button>
      </div>
    </div>
  )
}

function CategoryCabinet({ catalog, path, onChange }: StepProps) {
  const category = path.category
  const hint = path.result?.grade_up_hint
  const { unread, reload } = useUnreadMessages('candidate')
  return (
    <Cabinet title="Кабинет кандидата" upcoming={[]} unread={unread}>
      {category && (
        <div className="card">
          <span className="muted">Ваша категория</span>
          <p className="category-name">
            {category.specialization.name} · {category.grade.name}
          </p>
          {path.result && (
            <p>
              Уровень по тесту — <strong>{levelWords(path.result.overall.band)}</strong>.
            </p>
          )}
          {category.verified_at && <p className="success">Уровень подтверждён проверочным блоком.</p>}
          {hint && (
            <p className="success">Похоже, вам по силам и {gradeName(catalog, hint)} — стоит попробовать грейд выше.</p>
          )}
        </div>
      )}
      <VerificationCard catalog={catalog} path={path} onChange={onChange} />
      <GradeChangeCard catalog={catalog} path={path} onChange={onChange} />
      <Inbox onRead={reload} />
      <FeedbackCard onStartBlock={onChange} />
      <ProfileCard />
      <div className="card">
        <div className="section-head">
          <h2>Регулярные задания</h2>
          <Link to="/candidate/tasks" className="button button-small">
            Открыть каталог
          </Link>
        </div>
        <p>
          Задачи работодателей по вашей специализации: ответы уточняют профиль навыков и
          показывают, что уровень недавно подтверждён. Без новых сигналов уверенность в профиле со
          временем падает.
        </p>
      </div>
      {path.result && <TestResultView catalog={catalog} result={path.result} />}
      {path.profile && <SkillProfileView profile={path.profile} />}
      <HistoryView catalog={catalog} history={path.history} />
    </Cabinet>
  )
}
