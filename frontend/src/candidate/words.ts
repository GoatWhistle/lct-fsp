// Уровень и вероятности человеческим языком: «уверенно middle», «между junior и middle».
import type { Level } from '../api/client'

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

const number = new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 })

/** Уровень и погрешность на шкале θ: «0,8 ± 0,4». */
export function thetaWithError(level: Level): string {
  return `${number.format(level.theta)} ± ${number.format(level.theta_sd)}`
}

export function dateWords(iso: string): string {
  return new Date(iso).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
}
