import { useEffect, useState } from "react"
import { motionMs, prefersReducedMotion } from "@/shared/motion"

export function useEventCycle(count: number): number {
  const [index, setIndex] = useState(0)
  useEffect(() => {
    if (count < 2 || prefersReducedMotion()) return
    const timer = window.setInterval(
      () => setIndex((current) => (current + 1) % count),
      motionMs("--dur-signal"),
    )
    return () => window.clearInterval(timer)
  }, [count])
  return index
}
