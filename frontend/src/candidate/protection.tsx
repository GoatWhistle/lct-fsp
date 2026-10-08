// Защита теста на стороне кандидата: согласие на счётчики событий и таймер проверочного блока.
// Сервер всё равно решает сам: без согласия он счётчики отбрасывает, срок блока считает по своим
// часам. Сами счётчики — `focus.ts`.
import { useEffect, useRef, useState } from 'react'

type ConsentProps = { checked: boolean; onChange: (checked: boolean) => void }

/** Согласие перед тестом. Без него тест проходится так же — ничего не собирается. */
export function FocusConsent({ checked, onChange }: ConsentProps) {
  return (
    <label className="checkbox">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>
        Разрешаю считать вставки из буфера и уходы со вкладки во время теста. Только счётчики, без
        содержимого и записи экрана; они не влияют на оценку — много событий лишь предложат
        короткий проверочный блок. Без согласия тест проходится так же.
      </span>
    </label>
  )
}

function left(deadline: string): number {
  return Math.max(0, new Date(deadline).getTime() - Date.now())
}

/** Оставшееся время блока «мм:сс»; по истечении зовёт `onExpire` один раз. */
export function Countdown({ deadline, onExpire }: { deadline: string; onExpire: () => void }) {
  const [ms, setMs] = useState(() => left(deadline))
  const expired = useRef(false)

  useEffect(() => {
    const timer = window.setInterval(() => {
      const remaining = left(deadline)
      setMs(remaining)
      if (remaining === 0 && !expired.current) {
        expired.current = true
        onExpire()
      }
    }, 1000)
    return () => window.clearInterval(timer)
  }, [deadline, onExpire])

  const minutes = Math.floor(ms / 60000)
  const seconds = Math.floor((ms % 60000) / 1000)
  return (
    <span className={ms < 60000 ? 'tag warning' : 'tag'}>
      Осталось {minutes}:{String(seconds).padStart(2, '0')}
    </span>
  )
}
