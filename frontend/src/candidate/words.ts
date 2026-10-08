// Уровень и вероятности человеческим языком: «уверенно middle», «между junior и middle».
import type { HideableField, Level } from '../api/client'

/** Поля самоописания, которые кандидат может скрыть из обезличенной карточки, — в порядке анкеты. */
export const hideableFields: HideableField[] = ['stack', 'experience_years', 'city', 'relocation', 'industries']

export const hideableWords: Record<HideableField, string> = {
  stack: 'стек',
  experience_years: 'стаж',
  city: 'город',
  relocation: 'готовность к переезду',
  industries: 'интересные сферы',
}

const named: Record<string, string> = { intern: 'стажёр' }
const withWhom: Record<string, string> = { intern: 'стажёром' }

export function gradeWord(grade: string): string {
  return named[grade] ?? grade
}

export function levelWords(band: Level['band']): string {
  const { low, high } = band
  if (band.confident) return low ? `уверенно ${gradeWord(low)}` : 'ниже стажёра'
  if (!low) return 'стажёр или ниже'
  return `между ${withWhom[low] ?? low} и ${gradeWord(high ?? '')}`
}

/** Вероятность в процентах; края шкалы не округляются до «0 %» и «100 %». */
export function percent(probability: number): string {
  if (probability > 0.99) return '>99 %'
  if (probability < 0.01) return '<1 %'
  return `${Math.round(probability * 100)} %`
}

/** Число с одним знаком после запятой: «0,8». */
export const oneDecimal = new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 })

/** Уровень и погрешность на шкале θ: «0,8 ± 0,4». */
export function thetaWithError(level: Level): string {
  return `${oneDecimal.format(level.theta)} ± ${oneDecimal.format(level.theta_sd)}`
}

export function dateWords(iso: string): string {
  return new Date(iso).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
}

/** Дата и время: «6 октября 2026 г. в 12:37». */
export function dateTimeWords(iso: string): string {
  return new Date(iso).toLocaleString('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** Стаж словами: «меньше года», «1 год», «4 года», «11 лет». */
export function yearsWords(years: number): string {
  if (years === 0) return 'меньше года'
  const last = years % 10
  const lastTwo = years % 100
  if (last === 1 && lastTwo !== 11) return `${years} год`
  if (last >= 2 && last <= 4 && (lastTwo < 12 || lastTwo > 14)) return `${years} года`
  return `${years} лет`
}

/** Годы по технологии, кратные половине: «меньше полугода», «полгода», «1,5 года», «5 лет». */
export function technologyYearsWords(years: number): string {
  if (years < 0.5) return 'меньше полугода'
  if (years === 0.5) return 'полгода'
  if (!Number.isInteger(years)) return `${oneDecimal.format(years)} года`
  return yearsWords(years)
}

const months = [
  'январь',
  'февраль',
  'март',
  'апрель',
  'май',
  'июнь',
  'июль',
  'август',
  'сентябрь',
  'октябрь',
  'ноябрь',
  'декабрь',
]

/** Месяц `ГГГГ-ММ` словами: «март 2021». */
export function monthWords(month: string): string {
  const [year, number] = month.split('-')
  return `${months[Number(number) - 1]} ${year}`
}

/** Период записи опыта: «март 2021 — по сейчас». */
export function periodWords(start: string, end: string | null | undefined): string {
  return `${monthWords(start)} — ${end ? monthWords(end) : 'по сейчас'}`
}
