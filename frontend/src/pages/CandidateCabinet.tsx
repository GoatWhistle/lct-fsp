import { Cabinet } from '../components/Cabinet'

export function CandidateCabinet() {
  return (
    <Cabinet
      title="Кабинет кандидата"
      upcoming={[
        'Профиль: контакты, стек, ожидания по зарплате и формату',
        'Опрос по специализации и выбор грейда',
        'Тест и профиль навыков по темам',
        'Приглашения от работодателей',
      ]}
    />
  )
}
