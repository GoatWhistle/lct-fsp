// Счётчики событий за время задания — только при согласии кандидата на попытку (mechanics.md, §8).
import { useEffect, useRef } from 'react'

export type Counters = { paste_events: number; focus_losses: number }

/**
 * Счётчики событий за время текущего задания — только при согласии. `take` отдаёт накопленное
 * и обнуляет: у каждого задания свои.
 */
export function useFocusCounters(enabled: boolean): () => Counters {
  const counters = useRef<Counters>({ paste_events: 0, focus_losses: 0 })

  useEffect(() => {
    counters.current = { paste_events: 0, focus_losses: 0 }
    if (!enabled) return
    const onPaste = () => {
      counters.current.paste_events += 1
    }
    const onBlur = () => {
      counters.current.focus_losses += 1
    }
    document.addEventListener('paste', onPaste)
    window.addEventListener('blur', onBlur)
    return () => {
      document.removeEventListener('paste', onPaste)
      window.removeEventListener('blur', onBlur)
    }
  }, [enabled])

  return () => {
    const taken = counters.current
    counters.current = { paste_events: 0, focus_losses: 0 }
    return enabled ? taken : { paste_events: 0, focus_losses: 0 }
  }
}
