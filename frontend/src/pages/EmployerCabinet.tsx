import { Cabinet } from '../components/Cabinet'

export function EmployerCabinet() {
  return (
    <Cabinet
      title="Кабинет работодателя"
      upcoming={[
        'Профиль компании',
        'Потребность: кого ищете, стек, грейд, формат',
        'Подборка кандидатов с объяснением',
        'Приглашения и их статусы',
      ]}
    />
  )
}
