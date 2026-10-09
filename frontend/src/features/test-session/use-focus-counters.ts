import { useEffect, useRef } from "react"

export function useFocusCounters(enabled: boolean, itemId: string) {
  const counters = useRef({ paste_events: 0, focus_losses: 0 })
  useEffect(() => {
    counters.current = { paste_events: 0, focus_losses: 0 }
    if (!enabled || !itemId) return
    const onPaste = () => {
      counters.current.paste_events += 1
    }
    const onBlur = () => {
      counters.current.focus_losses += 1
    }
    document.addEventListener("paste", onPaste)
    window.addEventListener("blur", onBlur)
    return () => {
      document.removeEventListener("paste", onPaste)
      window.removeEventListener("blur", onBlur)
    }
  }, [enabled, itemId])
  return () => (enabled ? { ...counters.current } : { paste_events: 0, focus_losses: 0 })
}
