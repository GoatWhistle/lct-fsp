import { motionMs } from "./css-tokens"
import { prefersReducedMotion } from "./use-reduced-motion"

export function settleDelay(): number {
  return prefersReducedMotion() ? 0 : motionMs("--delay-settle")
}
