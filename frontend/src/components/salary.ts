/**
 * Деньги на платформе — рубли в месяц до вычета НДФЛ (гросс). Одна подпись для всех сумм:
 * ожидания кандидата, вилки потребности, приглашения и вакансии — поля в `SalaryInput.tsx`.
 */
export const SALARY_BASIS = 'до вычета НДФЛ'

const rubles = new Intl.NumberFormat('ru-RU')

/** «150 000 – 200 000 ₽ в месяц, до вычета НДФЛ»; без верхней границы — «от 150 000 ₽ …». */
export function salaryWords(from: number, to?: number): string {
  const amount =
    to === undefined
      ? `от ${rubles.format(from)}`
      : from === to
        ? rubles.format(from)
        : `${rubles.format(from)} – ${rubles.format(to)}`
  return `${amount} ₽ в месяц, ${SALARY_BASIS}`
}
