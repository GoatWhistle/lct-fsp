import { useEffect, useState } from "react"
import { motionMs } from "@/shared/motion"
import type { TraceStatus } from "@/shared/ui"

export const PARSE_STAGES = ["stageRead", "stageMatch", "stageDone"] as const

function useStage(pending: boolean, done: boolean): number {
  const [stage, setStage] = useState(0)
  useEffect(() => {
    if (!pending) return
    setStage(0)
    const timer = window.setTimeout(() => setStage(1), motionMs("--dur-draw"))
    return () => window.clearTimeout(timer)
  }, [pending])
  return done ? PARSE_STAGES.length - 1 : stage
}

export function useParseStatuses(pending: boolean, success: boolean): readonly TraceStatus[] {
  const stage = useStage(pending, success)
  return PARSE_STAGES.map((_, index): TraceStatus => {
    if (!pending && !success) return "upcoming"
    if (index < stage || (success && index === stage)) return "done"
    return index === stage ? "current" : "upcoming"
  })
}
