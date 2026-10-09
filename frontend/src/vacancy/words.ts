import type { InvitationStatus, Vacancy } from '../api/client'
import { salaryWords } from '../components/salary'
import { workFormatWord } from '../employer/words'

/** Статус отклика словами — для кандидата и работодателя одинаково; ход у работодателя. */
export const applicationStatusWords: Record<InvitationStatus, string> = {
  sent: 'отправлен',
  viewed: 'просмотрен',
  accepted: 'принят',
  declined: 'отклонён',
  expired: 'истёк без ответа',
}

/** Ждёт решения работодателя — то же правило, что у приглашения. */
export { isOpen } from '../invitation/words'

/** «Тестирование · Middle · Удалённо, Гибрид · 200 000 – 260 000 ₽ в месяц, до вычета НДФЛ». */
export function vacancyTermsWords(vacancy: Vacancy): string {
  return [
    `${vacancy.specialization.name} · ${vacancy.grade.name}`,
    vacancy.work_formats.map(workFormatWord).join(', '),
    salaryWords(vacancy.salary_from, vacancy.salary_to),
  ].join(' · ')
}
