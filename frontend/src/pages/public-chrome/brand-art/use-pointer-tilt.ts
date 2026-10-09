import { type RefObject, useEffect } from "react"
import { prefersReducedMotion } from "@/shared/motion"

const FINE_POINTER = "(hover: hover) and (pointer: fine)"
const NEAR_RADIUS = 96

function markNear(element: HTMLElement, event: PointerEvent): void {
  for (const group of element.querySelectorAll<SVGGElement>("[data-trace]")) {
    const near = [...group.querySelectorAll("circle")].some((node) => {
      const box = node.getBoundingClientRect()
      const distance = Math.hypot(
        event.clientX - (box.left + box.width / 2),
        event.clientY - (box.top + box.height / 2),
      )
      return distance < NEAR_RADIUS
    })
    group.dataset.near = String(near)
  }
}

function clampUnit(value: number): number {
  return Math.max(-1, Math.min(1, value))
}

export function usePointerTilt(ref: RefObject<HTMLElement | null>): void {
  useEffect(() => {
    const element = ref.current
    if (element === null || prefersReducedMotion()) return
    if (!window.matchMedia(FINE_POINTER).matches) return
    let frame = 0
    const onMove = (event: PointerEvent) => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        const box = element.getBoundingClientRect()
        const x = (event.clientX - (box.left + box.width / 2)) / (window.innerWidth / 2)
        const y = (event.clientY - (box.top + box.height / 2)) / (window.innerHeight / 2)
        element.style.setProperty("--pointer-x", clampUnit(x).toFixed(3))
        element.style.setProperty("--pointer-y", clampUnit(y).toFixed(3))
        markNear(element, event)
      })
    }
    window.addEventListener("pointermove", onMove, { passive: true })
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener("pointermove", onMove)
    }
  }, [ref])
}
