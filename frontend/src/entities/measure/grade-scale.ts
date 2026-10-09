import type { Level } from "@/shared/api"

export const GRADE_ORDER = ["intern", "junior", "middle", "senior"] as const

export type GradeCode = (typeof GRADE_ORDER)[number]

export const GRADE_THRESHOLD: Readonly<Record<GradeCode, number>> = {
  intern: -1.5,
  junior: -0.5,
  middle: 0.5,
  senior: 1.5,
}

export const SCALE_MIN = -2.5

export const SCALE_MAX = 2.5

export function isGradeCode(value: string): value is GradeCode {
  return (GRADE_ORDER as readonly string[]).includes(value)
}

export function scalePercent(theta: number): number {
  const clamped = Math.min(SCALE_MAX, Math.max(SCALE_MIN, theta))
  return ((clamped - SCALE_MIN) / (SCALE_MAX - SCALE_MIN)) * 100
}

export function spanPercent(width: number): number {
  return (width / (SCALE_MAX - SCALE_MIN)) * 100
}

export type UncertaintySize = "small" | "medium" | "large"

export function uncertaintySize(sd: number): UncertaintySize {
  if (sd < 0.35) return "small"
  if (sd < 0.7) return "medium"
  return "large"
}

export function gradeAt(theta: number): GradeCode | null {
  return [...GRADE_ORDER].reverse().find((grade) => theta >= GRADE_THRESHOLD[grade]) ?? null
}

export function levelFrom(theta: number, sd: number): Level {
  const low = gradeAt(theta - sd)
  const high = gradeAt(theta + sd)
  return { theta, theta_sd: sd, band: { low, high, confident: low === high } }
}
