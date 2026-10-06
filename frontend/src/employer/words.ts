import type { Need, TopicImportance, WorkFormat } from '../api/client'

export const workFormats: { value: WorkFormat; title: string }[] = [
  { value: 'office', title: 'Офис' },
  { value: 'hybrid', title: 'Гибрид' },
  { value: 'remote', title: 'Удалённо' },
]

export const importances: { value: TopicImportance; title: string }[] = [
  { value: 'key', title: 'Ключевая' },
  { value: 'important', title: 'Важная' },
  { value: 'nice', title: 'Желательная' },
]

export function workFormatWord(format: WorkFormat): string {
  return workFormats.find((f) => f.value === format)?.title ?? format
}

const rubles = new Intl.NumberFormat('ru-RU')

/** Вилка «от–до» в рублях в месяц или пометка, что её нет. */
export function salaryWords(need: Pick<Need, 'salary_from' | 'salary_to'>): string {
  const { salary_from: from, salary_to: to } = need
  if (from == null || to == null) return 'вилка не указана'
  if (from === to) return `${rubles.format(from)} ₽ в месяц`
  return `${rubles.format(from)} – ${rubles.format(to)} ₽ в месяц`
}
