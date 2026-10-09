import type { CSSProperties } from "react"

export type StaggerStyle = CSSProperties & { readonly "--i": number }

const STAGGER_STEPS = 8

export function staggerStyle(index: number): StaggerStyle {
  return { "--i": Math.min(STAGGER_STEPS, Math.max(0, Math.trunc(index))) }
}
